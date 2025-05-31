import os
from flask import Flask, request, send_file, jsonify
from werkzeug.utils import secure_filename
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from datetime import datetime
from extract_tables import extract_tables
from json_to_excel import json_to_excel
from io import BytesIO

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize PDF converter
converter = PdfConverter(
    artifact_dict=create_model_dict(),
)

def process_pdf(pdf_path):
    """Process PDF and return the extracted data"""
    rendered = converter(pdf_path)
    text, _, images = text_from_rendered(rendered)
    
    # Here you would add your specific processing logic
    # For now, we'll just return the text
    return text

@app.route('/webhook', methods=['POST'])
def webhook():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'File must be a PDF'}), 400

    try:
        # Save the uploaded file temporarily
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"{timestamp}_{filename}"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
        file.save(pdf_path)

        # Process the PDF
        extracted_text = process_pdf(pdf_path)
        table_strings = extract_tables(extracted_text)
        
        # Get DataFrame and Excel bytes from json_to_excel
        _, excel_bytes = json_to_excel(table_strings)
        
        if excel_bytes is None:
            return jsonify({'error': 'Failed to create Excel file'}), 500

        # Clean up the PDF file
        os.remove(pdf_path)

        # Create BytesIO object from the Excel bytes
        excel_buffer = BytesIO(excel_bytes)
        excel_buffer.seek(0)

        # Send the Excel file back to the client
        return send_file(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'extracted_data_{timestamp}.xlsx'
        )

    except Exception as e:
        # Clean up in case of error
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
