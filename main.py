import os
import json
from flask import Flask, request, send_file, jsonify
import pdfplumber
import pytesseract
from PIL import Image
import fitz  # PyMuPDF for image extraction

app = Flask(__name__)

def extract_text_from_pdf(pdf_path):
    """Extract text and tables from the PDF."""
    extracted_data = {"text": [], "tables": []}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Extract Text
            extracted_data["text"].append(page.extract_text())
            
            # Extract Tables
            for table in page.extract_tables():
                extracted_data["tables"].append(table)
    return extracted_data

def extract_images_from_pdf(pdf_path):
    """Extract images from the PDF."""
    images = []
    pdf_document = fitz.open(pdf_path)
    for page_number in range(len(pdf_document)):
        page = pdf_document[page_number]
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(io.BytesIO(image_bytes))
            images.append({"page": page_number + 1, "image_index": img_index + 1, "image": image})
    return images

def process_images_with_ocr(images):
    """Process extracted images with OCR to extract text."""
    ocr_results = []
    for image_data in images:
        text = pytesseract.image_to_string(image_data["image"])
        ocr_results.append({"page": image_data["page"], "image_index": image_data["image_index"], "text": text})
    return ocr_results

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload and process a PDF file."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    pdf_path = os.path.join("uploads", file.filename)
    file.save(pdf_path)
    
    # Extract text, tables, and images
    extracted_text_data = extract_text_from_pdf(pdf_path)
    extracted_images = extract_images_from_pdf(pdf_path)
    ocr_results = process_images_with_ocr(extracted_images)
    
    # Prepare JSON response
    response_data = {
        "overall_text": " ".join(extracted_text_data["text"][:20]),
        "tables": extracted_text_data["tables"][:20],
        "images": ocr_results[:20]
    }
    json_file_path = os.path.join("outputs", f"{file.filename}.json")
    with open(json_file_path, "w") as json_file:
        json.dump(response_data, json_file, indent=4)
    
    return jsonify({"message": "File processed successfully", "download_url": f"/download/{file.filename}.json"}), 200

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download the processed JSON file."""
    json_file_path = os.path.join("outputs", filename)
    if not os.path.exists(json_file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(json_file_path, as_attachment=True)

if __name__ == "__main__":
    # Ensure upload and output directories exist
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    
    # Run the Flask app
    app.run(debug=True)
