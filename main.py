"""
Pexel Document Studio - FastAPI Backend
A comprehensive PDF processing API with multiple tools
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import os
import uuid
import shutil
from typing import List, Optional
from pathlib import Path
import asyncio

# PDF processing imports
from pypdf import PdfReader, PdfWriter, PdfMerger
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from io import BytesIO

app = FastAPI(
    title="Pexel Document Studio API",
    description="Professional PDF tools API",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories for file storage
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def cleanup_file(filepath: Path, delay: int = 300):
    """Schedule file cleanup after delay seconds"""
    async def delete_after_delay():
        await asyncio.sleep(delay)
        if filepath.exists():
            filepath.unlink()
    asyncio.create_task(delete_after_delay())


@app.get("/")
async def root():
    return {"message": "Pexel Document Studio API", "status": "running"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


# ============== ORGANIZE TOOLS ==============

@app.post("/api/merge")
async def merge_pdfs(files: List[UploadFile] = File(...)):
    """Merge multiple PDF files into one"""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="At least 2 PDF files required")
    
    try:
        merger = PdfMerger()
        temp_files = []
        
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
            
            temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
            with open(temp_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            temp_files.append(temp_path)
            merger.append(str(temp_path))
        
        output_filename = f"merged_{uuid.uuid4().hex[:8]}.pdf"
        output_path = OUTPUT_DIR / output_filename
        merger.write(str(output_path))
        merger.close()
        
        # Cleanup temp files
        for temp_file in temp_files:
            temp_file.unlink()
        
        cleanup_file(output_path)
        
        return FileResponse(
            path=str(output_path),
            filename=output_filename,
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/split")
async def split_pdf(
    file: UploadFile = File(...),
    pages: str = Form(default="")
):
    """Split PDF into separate pages or specific page ranges"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        reader = PdfReader(str(temp_path))
        total_pages = len(reader.pages)
        
        # Parse page ranges or split all
        if pages:
            # Format: "1-3,5,7-9"
            page_nums = []
            for part in pages.split(','):
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    page_nums.extend(range(start - 1, min(end, total_pages)))
                else:
                    page_nums.append(int(part) - 1)
        else:
            page_nums = list(range(total_pages))
        
        output_files = []
        for i, page_num in enumerate(page_nums):
            if 0 <= page_num < total_pages:
                writer = PdfWriter()
                writer.add_page(reader.pages[page_num])
                
                output_filename = f"page_{page_num + 1}_{uuid.uuid4().hex[:6]}.pdf"
                output_path = OUTPUT_DIR / output_filename
                
                with open(output_path, "wb") as output_file:
                    writer.write(output_file)
                
                output_files.append(str(output_path))
                cleanup_file(output_path)
        
        temp_path.unlink()
        
        # Return first split file (in production, you'd zip all files)
        if output_files:
            return FileResponse(
                path=output_files[0],
                filename=f"split_{file.filename}",
                media_type="application/pdf"
            )
        else:
            raise HTTPException(status_code=400, detail="No valid pages to split")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/compress")
async def compress_pdf(
    file: UploadFile = File(...),
    quality: str = Form(default="medium")
):
    """Compress PDF to reduce file size"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        reader = PdfReader(str(temp_path))
        writer = PdfWriter()
        
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
        
        # Remove metadata to reduce size
        writer.add_metadata({})
        
        output_filename = f"compressed_{uuid.uuid4().hex[:8]}.pdf"
        output_path = OUTPUT_DIR / output_filename
        
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        
        original_size = temp_path.stat().st_size
        compressed_size = output_path.stat().st_size
        
        temp_path.unlink()
        cleanup_file(output_path)
        
        return FileResponse(
            path=str(output_path),
            filename=output_filename,
            media_type="application/pdf",
            headers={
                "X-Original-Size": str(original_size),
                "X-Compressed-Size": str(compressed_size),
                "X-Compression-Ratio": f"{(1 - compressed_size/original_size) * 100:.1f}%"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rotate")
async def rotate_pdf(
    file: UploadFile = File(...),
    angle: int = Form(default=90),
    pages: str = Form(default="all")
):
    """Rotate PDF pages by specified angle"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    if angle not in [90, 180, 270, -90, -180, -270]:
        raise HTTPException(status_code=400, detail="Angle must be 90, 180, or 270 degrees")
    
    try:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        reader = PdfReader(str(temp_path))
        writer = PdfWriter()
        
        total_pages = len(reader.pages)
        
        # Parse which pages to rotate
        if pages.lower() == "all":
            pages_to_rotate = set(range(total_pages))
        else:
            pages_to_rotate = set()
            for part in pages.split(','):
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    pages_to_rotate.update(range(start - 1, min(end, total_pages)))
                else:
                    pages_to_rotate.add(int(part) - 1)
        
        for i, page in enumerate(reader.pages):
            if i in pages_to_rotate:
                page.rotate(angle)
            writer.add_page(page)
        
        output_filename = f"rotated_{uuid.uuid4().hex[:8]}.pdf"
        output_path = OUTPUT_DIR / output_filename
        
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        
        temp_path.unlink()
        cleanup_file(output_path)
        
        return FileResponse(
            path=str(output_path),
            filename=output_filename,
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== CONVERT TOOLS ==============

@app.post("/api/pdf-to-images")
async def pdf_to_images(
    file: UploadFile = File(...),
    format: str = Form(default="png"),
    dpi: int = Form(default=150)
):
    """Convert PDF pages to images"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # For this demo, we'll create a placeholder image
        # In production, use pdf2image library with poppler
        reader = PdfReader(str(temp_path))
        first_page = reader.pages[0]
        
        # Create a simple image representation
        img = Image.new('RGB', (612, 792), color='white')
        
        output_filename = f"page_1.{format}"
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex[:8]}_{output_filename}"
        
        img.save(str(output_path), format.upper())
        
        temp_path.unlink()
        cleanup_file(output_path)
        
        media_type = f"image/{format}"
        return FileResponse(
            path=str(output_path),
            filename=output_filename,
            media_type=media_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/images-to-pdf")
async def images_to_pdf(files: List[UploadFile] = File(...)):
    """Convert multiple images to a single PDF"""
    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    
    try:
        images = []
        temp_files = []
        
        for file in files:
            ext = Path(file.filename).suffix.lower()
            if ext not in valid_extensions:
                raise HTTPException(
                    status_code=400, 
                    detail=f"File {file.filename} is not a valid image"
                )
            
            temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
            with open(temp_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            temp_files.append(temp_path)
            
            img = Image.open(temp_path)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            images.append(img)
        
        if not images:
            raise HTTPException(status_code=400, detail="No valid images provided")
        
        output_filename = f"images_to_pdf_{uuid.uuid4().hex[:8]}.pdf"
        output_path = OUTPUT_DIR / output_filename
        
        # Save first image with others appended
        first_image = images[0]
        other_images = images[1:] if len(images) > 1 else []
        
        first_image.save(
            str(output_path),
            "PDF",
            save_all=True if other_images else False,
            append_images=other_images if other_images else None
        )
        
        # Cleanup
        for img in images:
            img.close()
        for temp_file in temp_files:
            temp_file.unlink()
        
        cleanup_file(output_path)
        
        return FileResponse(
            path=str(output_path),
            filename=output_filename,
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== SECURITY TOOLS ==============

@app.post("/api/protect")
async def protect_pdf(
    file: UploadFile = File(...),
    password: str = Form(...)
):
    """Add password protection to PDF"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    if not password or len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    
    try:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        reader = PdfReader(str(temp_path))
        writer = PdfWriter()
        
        for page in reader.pages:
            writer.add_page(page)
        
        writer.encrypt(password)
        
        output_filename = f"protected_{uuid.uuid4().hex[:8]}.pdf"
        output_path = OUTPUT_DIR / output_filename
        
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        
        temp_path.unlink()
        cleanup_file(output_path)
        
        return FileResponse(
            path=str(output_path),
            filename=output_filename,
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/unlock")
async def unlock_pdf(
    file: UploadFile = File(...),
    password: str = Form(...)
):
    """Remove password protection from PDF"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        reader = PdfReader(str(temp_path))
        
        if reader.is_encrypted:
            if not reader.decrypt(password):
                raise HTTPException(status_code=400, detail="Incorrect password")
        
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        
        output_filename = f"unlocked_{uuid.uuid4().hex[:8]}.pdf"
        output_path = OUTPUT_DIR / output_filename
        
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        
        temp_path.unlink()
        cleanup_file(output_path)
        
        return FileResponse(
            path=str(output_path),
            filename=output_filename,
            media_type="application/pdf"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== EDIT TOOLS ==============

@app.post("/api/watermark")
async def add_watermark(
    file: UploadFile = File(...),
    text: str = Form(default="CONFIDENTIAL"),
    opacity: float = Form(default=0.3),
    position: str = Form(default="center")
):
    """Add text watermark to PDF"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        reader = PdfReader(str(temp_path))
        writer = PdfWriter()
        
        # Create watermark PDF
        watermark_buffer = BytesIO()
        c = canvas.Canvas(watermark_buffer, pagesize=letter)
        c.setFillAlpha(opacity)
        c.setFont("Helvetica-Bold", 60)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        
        # Rotate and position watermark
        c.saveState()
        c.translate(letter[0] / 2, letter[1] / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, text)
        c.restoreState()
        c.save()
        
        watermark_buffer.seek(0)
        watermark_pdf = PdfReader(watermark_buffer)
        watermark_page = watermark_pdf.pages[0]
        
        for page in reader.pages:
            page.merge_page(watermark_page)
            writer.add_page(page)
        
        output_filename = f"watermarked_{uuid.uuid4().hex[:8]}.pdf"
        output_path = OUTPUT_DIR / output_filename
        
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        
        temp_path.unlink()
        cleanup_file(output_path)
        
        return FileResponse(
            path=str(output_path),
            filename=output_filename,
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/add-page-numbers")
async def add_page_numbers(
    file: UploadFile = File(...),
    position: str = Form(default="bottom-center"),
    start_from: int = Form(default=1)
):
    """Add page numbers to PDF"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        reader = PdfReader(str(temp_path))
        writer = PdfWriter()
        
        for i, page in enumerate(reader.pages):
            # Create page number overlay
            page_num_buffer = BytesIO()
            c = canvas.Canvas(page_num_buffer, pagesize=letter)
            c.setFont("Helvetica", 10)
            c.setFillColorRGB(0, 0, 0)
            
            page_number = start_from + i
            
            if "bottom" in position:
                y = 30
            else:
                y = letter[1] - 30
            
            if "center" in position:
                x = letter[0] / 2
            elif "right" in position:
                x = letter[0] - 50
            else:
                x = 50
            
            c.drawCentredString(x, y, str(page_number))
            c.save()
            
            page_num_buffer.seek(0)
            page_num_pdf = PdfReader(page_num_buffer)
            page.merge_page(page_num_pdf.pages[0])
            writer.add_page(page)
        
        output_filename = f"numbered_{uuid.uuid4().hex[:8]}.pdf"
        output_path = OUTPUT_DIR / output_filename
        
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        
        temp_path.unlink()
        cleanup_file(output_path)
        
        return FileResponse(
            path=str(output_path),
            filename=output_filename,
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extract-text")
async def extract_text(file: UploadFile = File(...)):
    """Extract text content from PDF"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        reader = PdfReader(str(temp_path))
        
        extracted_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            extracted_text.append({
                "page": i + 1,
                "content": text
            })
        
        temp_path.unlink()
        
        return JSONResponse(content={
            "filename": file.filename,
            "total_pages": len(reader.pages),
            "pages": extracted_text
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/get-metadata")
async def get_metadata(file: UploadFile = File(...)):
    """Get PDF metadata information"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        reader = PdfReader(str(temp_path))
        
        metadata = reader.metadata
        info = {
            "filename": file.filename,
            "total_pages": len(reader.pages),
            "is_encrypted": reader.is_encrypted,
            "metadata": {
                "title": metadata.get("/Title", "") if metadata else "",
                "author": metadata.get("/Author", "") if metadata else "",
                "subject": metadata.get("/Subject", "") if metadata else "",
                "creator": metadata.get("/Creator", "") if metadata else "",
                "producer": metadata.get("/Producer", "") if metadata else "",
                "creation_date": str(metadata.get("/CreationDate", "")) if metadata else "",
                "modification_date": str(metadata.get("/ModDate", "")) if metadata else "",
            }
        }
        
        temp_path.unlink()
        
        return JSONResponse(content=info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
