# Pexel Document Studio - Backend API

A comprehensive FastAPI backend for PDF processing operations.

## Features

### Organize Tools
- **Merge** - Combine multiple PDFs into one
- **Split** - Separate PDF into multiple files
- **Compress** - Reduce file size
- **Rotate** - Rotate pages (90°, 180°, 270°)

### Convert Tools
- **PDF to Images** - Export pages as PNG/JPG
- **Images to PDF** - Create PDF from images

### Security Tools
- **Protect** - Add password encryption
- **Unlock** - Remove password protection

### Edit Tools
- **Watermark** - Add text watermark
- **Page Numbers** - Add page numbering

### Utility Tools
- **Extract Text** - Get text content from PDF
- **Get Metadata** - Retrieve PDF information

## Quick Start

### Using Python directly

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Using Docker

```bash
# Build the image
docker build -t pexel-backend .

# Run the container
docker run -p 8000:8000 pexel-backend
```

### Using Docker Compose (recommended)

```bash
# From the project root directory
docker-compose up --build
```

## API Endpoints

### Health Check
```
GET /api/health
```

### Merge PDFs
```
POST /api/merge
Content-Type: multipart/form-data
- files: PDF files (multiple)
```

### Split PDF
```
POST /api/split
Content-Type: multipart/form-data
- file: PDF file
- pages: (optional) Page ranges, e.g., "1-3,5,7-9"
```

### Compress PDF
```
POST /api/compress
Content-Type: multipart/form-data
- file: PDF file
- quality: "low" | "medium" | "high"
```

### Rotate PDF
```
POST /api/rotate
Content-Type: multipart/form-data
- file: PDF file
- angle: 90 | 180 | 270
- pages: "all" or specific pages like "1-3,5"
```

### Protect PDF
```
POST /api/protect
Content-Type: multipart/form-data
- file: PDF file
- password: Password string
```

### Unlock PDF
```
POST /api/unlock
Content-Type: multipart/form-data
- file: PDF file
- password: Current password
```

### Add Watermark
```
POST /api/watermark
Content-Type: multipart/form-data
- file: PDF file
- text: Watermark text
- opacity: 0.0 - 1.0
- position: "center" | "top" | "bottom"
```

### PDF to Images
```
POST /api/pdf-to-images
Content-Type: multipart/form-data
- file: PDF file
- format: "png" | "jpg"
- dpi: Resolution (default 150)
```

### Images to PDF
```
POST /api/images-to-pdf
Content-Type: multipart/form-data
- files: Image files (multiple)
```

### Extract Text
```
POST /api/extract-text
Content-Type: multipart/form-data
- file: PDF file
Returns: JSON with extracted text
```

### Get Metadata
```
POST /api/get-metadata
Content-Type: multipart/form-data
- file: PDF file
Returns: JSON with PDF metadata
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| HOST | Server host | 0.0.0.0 |
| PORT | Server port | 8000 |

## File Cleanup

Processed files are automatically deleted after 5 minutes (300 seconds) to save disk space.

## CORS

CORS is enabled for all origins by default. For production, update the `allow_origins` list in `main.py`.

## License

MIT License
