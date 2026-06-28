# Marathi Scene Text Annotation Platform

A Human-in-the-Loop OCR-assisted annotation tool for Marathi scene text dataset creation.

## Stack
- **Frontend**: Next.js 14 + TypeScript + TailwindCSS
- **Backend**: FastAPI (Python)
- **Database**: SQLite (upgradeable to PostgreSQL)
- **OCR**: IndicPhotoOCR

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
