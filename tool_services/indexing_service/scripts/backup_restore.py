import json
import sqlite3
import argparse
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import chromadb
from app.core.config import settings
from app.models.doc import Doc
from app.models.chunk import Chunk

def export_data(output_file):
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    data = {
        "docs": [],
        "chunks": []
    }
    
    docs = db.query(Doc).all()
    for d in docs:
        doc_dict = {c.name: getattr(d, c.name) for c in d.__table__.columns}
        data["docs"].append(doc_dict)
        
    chunks = db.query(Chunk).all()
    for c in chunks:
        chunk_dict = {col.name: getattr(c, col.name) for col in c.__table__.columns}
        data["chunks"].append(chunk_dict)
        
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Exported {len(data['docs'])} docs and {len(data['chunks'])} chunks to {output_file}")
    db.close()

def import_data(input_file):
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for d_dict in data["docs"]:
        doc = Doc(**d_dict)
        db.merge(doc)
        
    for c_dict in data["chunks"]:
        chunk = Chunk(**c_dict)
        db.merge(chunk)
        
    db.commit()
    print(f"Imported {len(data['docs'])} docs and {len(data['chunks'])} chunks from {input_file}")
    db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indexing Service Backup/Restore")
    parser.add_argument("action", choices=["export", "import"])
    parser.add_argument("--file", default="backup.json")
    
    args = parser.parse_args()
    
    if args.action == "export":
        export_data(args.file)
    else:
        import_data(args.file)

