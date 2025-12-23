import asyncio
import json
import uuid
import sys
import os
import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message

# 将项目根目录添加到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.common import RabbitConfig, MessagePackage, MsgHeader, CommandPayload, MockStorage

class NexusService:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue_name = "q.nexus.orchestrator"

    def _ctx_key(self, trace_id: str) -> str:
        return f"task:{trace_id}:ctx"

    async def _ctx_update(self, trace_id: str, **kwargs):
        key = self._ctx_key(trace_id)
        ctx = await MockStorage.get(key) or {}
        if not isinstance(ctx, dict):
            ctx = {}
        ctx.update({k: v for k, v in kwargs.items() if v is not None})
        await MockStorage.save(key, ctx)
        return ctx

    def _extract_work_key_from_any_key(self, key: str) -> str:
        """
        从 downloader/parse/index 的 output_key 中反推出 work_key。
        work_key 是我们 fan-out 时创建的：task:{trace_id}:work:{i}
        """
        s = str(key or "")
        marker = "data:download:"
        if marker in s:
            return s.split(marker, 1)[1]
        # 如果是 downloader 的 key：data:download:{work_key}
        if s.startswith("data:download:"):
            return s[len("data:download:") :]
        raise ValueError(f"cannot extract work_key from key={key}")

    def _work_has_pdf_candidate(self, work: dict) -> bool:
        if not isinstance(work, dict):
            return False
        bol = work.get("best_oa_location") or {}
        if isinstance(bol, dict) and bol.get("pdf_url"):
            return True
        locs = work.get("locations") or []
        if isinstance(locs, list):
            for loc in locs:
                if isinstance(loc, dict) and loc.get("pdf_url"):
                    return True
        # arXiv landing_page_url abs 兜底（不是伪造，是可解析的真实 url 变体）
        if isinstance(bol, dict):
            lp = str(bol.get("landing_page_url") or "")
            if "arxiv.org/abs/" in lp:
                return True
        return False

    def _infer_work_key(self, trace_id: str, any_key: str) -> str:
        """
        失败/成功事件里可能出现：
        - work_key: task:{trace_id}:work:{i}
        - download_key/parse_key/index_key（都包含 data:download:task:{trace_id}:work:{i}）
        """
        s = str(any_key or "")
        prefix = f"task:{trace_id}:work:"
        if s.startswith(prefix):
            return s
        if "data:download:" in s:
            return s.split("data:download:", 1)[1]
        raise ValueError(f"cannot infer work_key from any_key={any_key}")

    async def _maybe_finalize_morning_report(self, trace_id: str) -> None:
        ctx = await MockStorage.get(self._ctx_key(trace_id)) or {}
        if not isinstance(ctx, dict):
            return
        work_keys = ctx.get("work_keys") or []
        if not isinstance(work_keys, list) or not work_keys:
            return
        completed = ctx.get("completed_work_keys") or []
        failures = ctx.get("failures") or []
        if not isinstance(completed, list):
            completed = []
        if not isinstance(failures, list):
            failures = []

        done_set = set([wk for wk in completed if isinstance(wk, str)])
        for f in failures:
            if isinstance(f, dict) and isinstance(f.get("work_key"), str):
                done_set.add(f["work_key"])

        if len(done_set) >= len(work_keys) and not ctx.get("report_key"):
            report_key = await self._build_and_persist_morning_report(trace_id)
            await self._ctx_update(trace_id, report_key=report_key)
            print(f"[Nexus] ✅ Job {trace_id} Completed (partial failures allowed)! Report at: {report_key}")

    async def _maybe_finalize_summary_report(self, trace_id: str) -> None:
        ctx = await MockStorage.get(self._ctx_key(trace_id)) or {}
        if not isinstance(ctx, dict):
            return
        paper_in_keys = ctx.get("paper_in_keys") or []
        if not isinstance(paper_in_keys, list) or not paper_in_keys:
            return

        completed = ctx.get("completed_paper_in_keys") or []
        failures = ctx.get("paper_failures") or []
        if not isinstance(completed, list):
            completed = []
        if not isinstance(failures, list):
            failures = []

        done_set = set([k for k in completed if isinstance(k, str)])
        for f in failures:
            if isinstance(f, dict) and isinstance(f.get("paper_in_key"), str):
                done_set.add(f["paper_in_key"])

        if len(done_set) >= len(paper_in_keys) and not ctx.get("overview_in_key"):
            # 聚合成功的 llm_summary，触发 overview
            summaries = []
            for pik in completed:
                parse_key = f"data:parse:{pik}"
                parse_payload = await MockStorage.get(parse_key)
                paper_payload = await MockStorage.get(pik)
                if not isinstance(parse_payload, dict) or not isinstance(paper_payload, dict):
                    continue
                llm_summary = (parse_payload.get("llm_summary") or "").strip()
                if not llm_summary:
                    continue
                paper = {
                    "title": paper_payload.get("title"),
                    "authors": paper_payload.get("authors") or [],
                    "pdf_url": paper_payload.get("pdf_url"),
                }
                summaries.append({"paper": paper, "llm_summary": llm_summary})

            if not summaries:
                raise RuntimeError("no successful llm_summary to build overview")

            overview_in_key = f"task:{trace_id}:overview_in"
            await MockStorage.save(
                overview_in_key,
                {
                    "summaries": summaries,
                    "target_lang": "en",
                    "domain": (ctx.get("domain") or "").strip(),
                    "style": (ctx.get("style") or "academic").strip(),
                },
            )
            await self._ctx_update(trace_id, overview_in_key=overview_in_key)
            await self._send_command(trace_id, "SUMMARY_REPORT", "cmd.overview.start", overview_in_key)
            print(f"[Nexus] SUMMARY_REPORT: triggered overview generation for {len(summaries)} papers")

    async def _build_and_persist_summary_report(self, trace_id: str, overview_out_key: str) -> str:
        ctx = await MockStorage.get(self._ctx_key(trace_id)) or {}
        if not isinstance(ctx, dict):
            raise RuntimeError("trace ctx missing or invalid")

        init_key = ctx.get("init_key")
        summary_report_key_in = ctx.get("summary_report_key_in")
        paper_in_keys = ctx.get("paper_in_keys") or []
        completed = ctx.get("completed_paper_in_keys") or []
        failures = ctx.get("paper_failures") or []
        if not isinstance(completed, list):
            completed = []
        if not isinstance(failures, list):
            failures = []

        init_payload = await MockStorage.get(init_key) if init_key else {}
        overview_payload = await MockStorage.get(overview_out_key)
        if not isinstance(overview_payload, dict):
            raise RuntimeError("overview payload missing")

        papers = []
        for pik in completed:
            parse_key = f"data:parse:{pik}"
            parse_payload = await MockStorage.get(parse_key)
            paper_payload = await MockStorage.get(pik)
            if not isinstance(parse_payload, dict) or not isinstance(paper_payload, dict):
                continue
            papers.append(
                {
                    "paper": {
                        "title": paper_payload.get("title"),
                        "authors": paper_payload.get("authors") or [],
                        "pdf_url": paper_payload.get("pdf_url"),
                    },
                    "llm_summary": parse_payload.get("llm_summary", ""),
                    "keys": {"paper_in_key": pik, "parse_key": parse_key},
                }
            )

        report = {
            "trace_id": trace_id,
            "task_type": "SUMMARY_REPORT",
            "paper_count": len(papers),
            "papers": papers,
            "failure_count": len(failures),
            "failures": failures,
            "overview_key": overview_out_key,
            "overview_md": overview_payload.get("overview_md", ""),
            "keys": {"init_key": init_key, "summary_report_key_in": summary_report_key_in},
            "input": init_payload if isinstance(init_payload, dict) else {},
        }

        report_key = f"data:summary_report:{trace_id}"
        await MockStorage.save(report_key, report)
        print("[Nexus] SummaryReport saved:", report_key)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report_key

    async def _build_and_persist_morning_report(self, trace_id: str) -> str:
        ctx = await MockStorage.get(self._ctx_key(trace_id)) or {}
        if not isinstance(ctx, dict):
            raise RuntimeError("trace ctx missing or invalid")

        init_key = ctx.get("init_key")
        discovery_key = ctx.get("discovery_key")
        work_keys = ctx.get("work_keys") or []
        if not isinstance(work_keys, list) or not work_keys:
            raise RuntimeError("work_keys missing or empty")

        init_payload = await MockStorage.get(init_key) if init_key else {}
        requested_limit = ctx.get("requested_limit")
        failures = ctx.get("failures") or []
        if not isinstance(failures, list):
            failures = []

        papers = []
        completed_work_keys = ctx.get("completed_work_keys") or []
        if not isinstance(completed_work_keys, list):
            completed_work_keys = []
        for wk in completed_work_keys:
            if not isinstance(wk, str) or not wk:
                continue
            download_key = f"data:download:{wk}"
            parse_key = f"data:parse:{download_key}"
            index_key = f"data:index:{parse_key}"

            download_payload = await MockStorage.get(download_key)
            parse_payload = await MockStorage.get(parse_key)
            index_payload = await MockStorage.get(index_key)

            if not isinstance(download_payload, dict) or not isinstance(parse_payload, dict) or not isinstance(index_payload, dict):
                # 成功列表里不应出现缺失；若出现则视为内部错误
                raise RuntimeError(f"missing downstream payload for completed work_key={wk}")

            work = download_payload.get("work") or {}
            if not isinstance(work, dict):
                work = {}

            papers.append(
                {
                    "paper": {
                        "title": work.get("title") or download_payload.get("filename"),
                        "authors": work.get("authors") or [],
                        "pdf_url": download_payload.get("pdf_url"),
                        "openalex_id": work.get("openalex_id") or work.get("id"),
                        "doi": work.get("doi"),
                        "publication_date": work.get("publication_date"),
                        "original_url": download_payload.get("source_url"),
                    },
                    "summary": {"llm_summary": parse_payload.get("llm_summary", "")},
                    "index": {
                        "collection": index_payload.get("collection"),
                        "vector_count": index_payload.get("vector_count"),
                        "persist_dir": index_payload.get("persist_dir"),
                    },
                    "keys": {
                        "work_key": wk,
                        "download_key": download_key,
                        "parse_key": parse_key,
                        "index_key": index_key,
                    },
                }
            )

        report = {
            "trace_id": trace_id,
            "task_type": "MORNING_REPORT",
            "requested_limit": requested_limit,
            "paper_count": len(papers),
            "papers": papers,
            "failure_count": len(failures),
            "failures": failures,
            "keys": {
                "init_key": init_key,
                "discovery_key": discovery_key,
            },
            "input": {
                "query": (init_payload or {}).get("query") if isinstance(init_payload, dict) else None,
                "filters": (init_payload or {}).get("filters") if isinstance(init_payload, dict) else None,
            },
        }

        report_key = f"data:morning_report:{trace_id}"
        await MockStorage.save(report_key, report)
        print("[Nexus] MorningReport saved:", report_key)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report_key

    async def connect(self):
        self.connection = await aio_pika.connect_robust(RabbitConfig.URL)
        self.channel = await self.connection.channel()
        
        # 声明交换机 (幂等)
        await self.channel.declare_exchange(RabbitConfig.CMD_EXCHANGE, ExchangeType.DIRECT, durable=True)
        evt_exchange = await self.channel.declare_exchange(RabbitConfig.EVT_EXCHANGE, ExchangeType.TOPIC, durable=True)
        
        # 声明监听队列
        queue = await self.channel.declare_queue(self.queue_name, durable=True)
        # 监听所有事件
        await queue.bind(evt_exchange, routing_key="evt.#")
        
        return queue

    async def start(self):
        print("[*] Nexus Orchestrator Started. Listening for events...")
        queue = await self.connect()
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    await self._on_event(message)

    async def submit_job(self, task_type: str, initial_data: dict):
        """API 入口点"""
        # 如果单独调用，确保连接存在
        if not self.channel:
            await self.connect()
            
        trace_id = str(uuid.uuid4())
        print(f"\n[Nexus] >>> New Job Received: {task_type} | TraceID: {trace_id}")
        
        # 1. Claim Check (保存数据)
        input_key = f"task:{trace_id}:init"
        await MockStorage.save(input_key, initial_data)
        requested_limit = int((initial_data or {}).get("limit", 5)) if isinstance(initial_data, dict) else 5
        await self._ctx_update(
            trace_id,
            init_key=input_key,
            requested_limit=requested_limit,
            work_keys=[],
            completed_work_keys=[],
        )
        
        # 2. 触发第一步
        if task_type == "MORNING_REPORT":
            # MORNING_REPORT: discovery -> downloader -> parser -> indexer
            await self._send_command(trace_id, task_type, "cmd.discovery.start", input_key)
        elif task_type == "SUMMARY_REPORT":
            # SUMMARY_REPORT: init contains summary_report_key -> fan-out parser -> overview -> finalize report
            summary_report_key_in = (initial_data or {}).get("summary_report_key") if isinstance(initial_data, dict) else None
            if not summary_report_key_in:
                raise ValueError("SUMMARY_REPORT requires initial_data.summary_report_key")
            sr = await MockStorage.get(summary_report_key_in)
            if not isinstance(sr, dict):
                raise ValueError("summary_report_key must point to a dict payload")
            papers = sr.get("papers") or []
            if not isinstance(papers, list) or not papers:
                raise ValueError("summary_report papers must be a non-empty list")

            paper_in_keys = []
            for i, p in enumerate(papers, start=1):
                if not isinstance(p, dict):
                    continue
                pdf_url = (p.get("pdf_url") or "").strip()
                if not pdf_url:
                    continue
                pik = f"task:{trace_id}:paper:{i}"
                await MockStorage.save(
                    pik,
                    {
                        "pdf_url": pdf_url,
                        "title": p.get("title"),
                        "authors": p.get("authors") or [],
                        "source_url": pdf_url,
                        "content_type": "application/pdf",
                    },
                )
                paper_in_keys.append(pik)
                await self._send_command(trace_id, task_type, "cmd.parser.start", pik)

            if not paper_in_keys:
                raise RuntimeError("no valid pdf_url in summary_report papers")

            await self._ctx_update(
                trace_id,
                summary_report_key_in=summary_report_key_in,
                paper_in_keys=paper_in_keys,
                completed_paper_in_keys=[],
                paper_failures=[],
                domain=sr.get("domain") or "",
                style=sr.get("style") or "academic",
            )
            print(f"[Nexus] SUMMARY_REPORT: scheduled {len(paper_in_keys)} papers for parsing")
            
        return trace_id

    async def _on_event(self, message: aio_pika.abc.AbstractIncomingMessage):
        body_str = message.body.decode()
        pkg = MessagePackage(**json.loads(body_str))
        routing_key = message.routing_key
        trace_id = pkg.header.trace_id
        
        print(f"[Nexus] Received Event: {routing_key} | TraceID: {trace_id}")
        
        if pkg.payload['status'] == 'FAIL':
             # 允许部分失败：MORNING_REPORT / SUMMARY_REPORT 的 fan-out 阶段记录 failures[]，不 fail-fast
             err = pkg.payload.get("error_msg")
             in_key = pkg.payload.get("input_key")
             print(f"[Nexus] 🚨 Task Failed at {pkg.header.sender}: {err}")

             ctx = await MockStorage.get(self._ctx_key(trace_id)) or {}
             # MORNING_REPORT failures（work_keys）
             if isinstance(ctx, dict) and isinstance(ctx.get("work_keys"), list) and ctx.get("work_keys"):
                 try:
                     wk = self._infer_work_key(trace_id, in_key)
                 except Exception:
                     # 无法定位到某篇 work 的失败（例如 discovery/init）仍视为全局失败
                     return

                 failures = ctx.get("failures") or []
                 if not isinstance(failures, list):
                     failures = []
                 failures.append(
                     {
                         "work_key": wk,
                         "stage": pkg.header.sender,
                         "routing_key": routing_key,
                         "input_key": in_key,
                         "error_msg": err,
                     }
                 )
                 await self._ctx_update(trace_id, failures=failures)
                 await self._maybe_finalize_morning_report(trace_id)
                 return

             # SUMMARY_REPORT failures（paper_in_keys）
             if isinstance(ctx, dict) and isinstance(ctx.get("paper_in_keys"), list) and ctx.get("paper_in_keys"):
                 paper_in_key = str(in_key or "").strip()
                 if not paper_in_key:
                     # 无法定位到某篇 paper 的失败：视为全局失败
                     return
                 failures = ctx.get("paper_failures") or []
                 if not isinstance(failures, list):
                     failures = []
                 failures.append(
                     {
                         "paper_in_key": paper_in_key,
                         "stage": pkg.header.sender,
                         "routing_key": routing_key,
                         "input_key": in_key,
                         "error_msg": err,
                     }
                 )
                 await self._ctx_update(trace_id, paper_failures=failures)
                 await self._maybe_finalize_summary_report(trace_id)
                 return
             return

        # --- DAG 逻辑 ---
        if pkg.header.task_type == "MORNING_REPORT":
            
            if routing_key == "evt.discovery.finished":
                discovery_out_key = pkg.payload["output_key"]
                ctx = await self._ctx_update(trace_id, discovery_key=discovery_out_key)

                discovery_payload = await MockStorage.get(discovery_out_key)
                if not isinstance(discovery_payload, dict):
                    raise RuntimeError("discovery payload invalid")

                results = discovery_payload.get("results") or []
                if not isinstance(results, list):
                    raise RuntimeError("discovery results invalid")

                requested_limit = int(ctx.get("requested_limit", 5))
                # 只调度“看起来有 pdf 候选”的 work，避免 downstream 报错
                sched_works = [w for w in results if isinstance(w, dict) and self._work_has_pdf_candidate(w)]
                sched_works = sched_works[:requested_limit]
                if not sched_works:
                    raise RuntimeError("no works with downloadable pdf_url candidates found")

                work_keys = []
                for i, work in enumerate(sched_works, start=1):
                    wk = f"task:{trace_id}:work:{i}"
                    await MockStorage.save(wk, {"work": work, "timeout": 30})
                    work_keys.append(wk)
                    await self._send_command(trace_id, pkg.header.task_type, "cmd.downloader.start", wk)

                await self._ctx_update(trace_id, work_keys=work_keys)
                print(f"[Nexus] Scheduled {len(work_keys)} papers for download (requested_limit={requested_limit})")

            elif routing_key == "evt.downloader.finished":
                print("[Nexus] Scheduling Next Step: Parser")
                await self._send_command(trace_id, pkg.header.task_type, "cmd.parser.start", pkg.payload['output_key'])
                
            elif routing_key == "evt.parser.finished":
                print("[Nexus] Scheduling Next Step: Indexer")
                await self._send_command(trace_id, pkg.header.task_type, "cmd.indexer.start", pkg.payload['output_key'])
                
            elif routing_key == "evt.indexer.finished":
                # 记录完成的 work_key，直到全部 work 都完成才产出总 report
                index_out_key = pkg.payload["output_key"]
                wk = self._infer_work_key(trace_id, index_out_key)
                ctx = await MockStorage.get(self._ctx_key(trace_id)) or {}
                if not isinstance(ctx, dict):
                    ctx = {}
                completed = ctx.get("completed_work_keys") or []
                if not isinstance(completed, list):
                    completed = []
                if wk not in completed:
                    completed.append(wk)
                await self._ctx_update(trace_id, completed_work_keys=completed)
                await self._maybe_finalize_morning_report(trace_id)

        elif pkg.header.task_type == "SUMMARY_REPORT":
            # 失败：记录到 paper_failures（若能定位到 paper_in_key），并尝试 finalize
            if routing_key.endswith(".failed"):
                return

            if routing_key == "evt.parser.finished":
                paper_in_key = pkg.payload.get("input_key") or pkg.payload.get("output_key", "")
                # 对于 SUCCESS，我们从 output_key 反推 paper_in_key
                # parse output_key 形如 data:parse:{paper_in_key}
                out_key = pkg.payload.get("output_key") or ""
                if isinstance(out_key, str) and out_key.startswith("data:parse:"):
                    paper_in_key = out_key[len("data:parse:") :]

                ctx = await MockStorage.get(self._ctx_key(trace_id)) or {}
                completed = (ctx.get("completed_paper_in_keys") or []) if isinstance(ctx, dict) else []
                if not isinstance(completed, list):
                    completed = []
                if paper_in_key and paper_in_key not in completed:
                    completed.append(paper_in_key)
                await self._ctx_update(trace_id, completed_paper_in_keys=completed)
                await self._maybe_finalize_summary_report(trace_id)

            elif routing_key == "evt.overview.finished":
                overview_out_key = pkg.payload.get("output_key")
                report_key = await self._build_and_persist_summary_report(trace_id, overview_out_key)
                await self._ctx_update(trace_id, summary_report_out_key=report_key)
                print(f"[Nexus] ✅ SUMMARY_REPORT {trace_id} Completed! Report at: {report_key}")

    async def _send_command(self, trace_id, task_type, routing_key, input_key):
        header = MsgHeader(trace_id=trace_id, task_type=task_type, sender="nexus")
        payload = CommandPayload(task_id=str(uuid.uuid4()), input_key=input_key)
        pkg = MessagePackage(header=header, payload=payload.model_dump())
        
        exchange = await self.channel.get_exchange(RabbitConfig.CMD_EXCHANGE)
        
        await exchange.publish(
            Message(
                body=pkg.model_dump_json().encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            ),
            routing_key=routing_key
        )
        print(f"[Nexus] Sent Command: {routing_key}")
