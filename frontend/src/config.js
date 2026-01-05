/**
 * 应用配置
 * 所有服务器 URL 从环境变量读取
 */

// 后端API基础URL
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

if (!API_BASE_URL) {
  console.error('错误: 未设置环境变量 VITE_API_BASE_URL')
  throw new Error('VITE_API_BASE_URL 环境变量未设置，请在 .env 文件中配置')
}

// MinIO上传服务器URL
export const MINIO_UPLOAD_URL = import.meta.env.VITE_MINIO_UPLOAD_URL

if (!MINIO_UPLOAD_URL) {
  console.error('错误: 未设置环境变量 VITE_MINIO_UPLOAD_URL')
  throw new Error('VITE_MINIO_UPLOAD_URL 环境变量未设置，请在 .env 文件中配置')
}

