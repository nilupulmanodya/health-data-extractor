import os
from flask import Flask, request, send_file, jsonify
from werkzeug.utils import secure_filename
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
import pandas as pd
import tempfile
from datetime import datetime

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
        print("extracted_text", extracted_text)
        os.remove(pdf_path)

        

        # # Create a temporary Excel file
        # with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        #     # Convert the extracted text to a DataFrame
        #     # You might want to modify this based on your specific data structure
        #     df = pd.DataFrame({'Extracted Text': [extracted_text]})
        #     df.to_excel(tmp.name, index=False)
            
        #     # Clean up the temporary PDF
        #     os.remove(pdf_path)
            
        #     # Send the Excel file
        #     return send_file(
        #         tmp.name,
        #         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        #         as_attachment=True,
        #         download_name=f'extracted_data_{timestamp}.xlsx'
        #     )
        return jsonify({'extracted_text': extracted_text})

    except Exception as e:
        # Clean up in case of error
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
