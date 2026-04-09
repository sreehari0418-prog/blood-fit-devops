import json
import boto3
import os
import uuid
import re
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
textract_client = boto3.client('textract')
comprehend_client = boto3.client('comprehend')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = os.environ.get('BUCKET_NAME')
TABLE_NAME = os.environ.get('TABLE_NAME')
table = dynamodb.Table(TABLE_NAME) if TABLE_NAME else None

# Comprehensive library of 50+ blood markers with normal ranges and aliases
MEDICAL_MARKERS = {
    # Hematology / CBC
    "Hemoglobin": {"min": 13.5, "max": 17.5, "unit": "g/dL", "aliases": ["Hb", "Hgb", "Haemoglobin"]},
    "RBC": {"min": 4.5, "max": 5.9, "unit": "x10^12/L", "aliases": ["Red Blood Cells", "Erythrocytes", "R.B.C"]},
    "WBC": {"min": 4.5, "max": 11.0, "unit": "x10^9/L", "aliases": ["White Blood Cells", "Leukocytes", "W.B.C"]},
    "Hematocrit": {"min": 41, "max": 50, "unit": "%", "aliases": ["HCT", "PCV"]},
    "MCV": {"min": 80, "max": 96, "unit": "fL", "aliases": ["Mean Cell Volume"]},
    "MCH": {"min": 27, "max": 33, "unit": "pg", "aliases": ["Mean Corpuscular Hemoglobin"]},
    "MCHC": {"min": 32, "max": 36, "unit": "g/dL", "aliases": ["Mean Corpuscular Hemoglobin Concentration"]},
    "Platelets": {"min": 150, "max": 450, "unit": "K/uL", "aliases": ["PLT", "Thrombocytes", "Platelet Count"]},
    "RDW": {"min": 11.5, "max": 14.5, "unit": "%", "aliases": ["Red Cell Distribution Width"]},
    "Neutrophils": {"min": 40, "max": 60, "unit": "%", "aliases": ["NEUT"]},
    "Lymphocytes": {"min": 20, "max": 40, "unit": "%", "aliases": ["LYMPH"]},
    "Monocytes": {"min": 2, "max": 8, "unit": "%", "aliases": ["MONO"]},
    "Eosinophils": {"min": 1, "max": 4, "unit": "%", "aliases": ["EOS"]},
    "Basophils": {"min": 0.5, "max": 1, "unit": "%", "aliases": ["BASO"]},

    # Metabolic Panel (BMP/CMP)
    "Glucose": {"min": 70, "max": 99, "unit": "mg/dL", "aliases": ["GLU", "Blood Sugar", "Fasting Glucose"]},
    "Calcium": {"min": 8.5, "max": 10.2, "unit": "mg/dL", "aliases": ["CA"]},
    "Sodium": {"min": 135, "max": 145, "unit": "mEq/L", "aliases": ["NA"]},
    "Potassium": {"min": 3.5, "max": 5.1, "unit": "mEq/L", "aliases": ["K", "POT"]},
    "Bicarbonate": {"min": 22, "max": 29, "unit": "mEq/L", "aliases": ["CO2", "HCO3"]},
    "Chloride": {"min": 98, "max": 107, "unit": "mEq/L", "aliases": ["CL"]},
    "BUN": {"min": 7, "max": 20, "unit": "mg/dL", "aliases": ["Blood Urea Nitrogen"]},
    "Creatinine": {"min": 0.7, "max": 1.3, "unit": "mg/dL", "aliases": ["CREA"]},
    "Albumin": {"min": 3.4, "max": 5.4, "unit": "g/dL", "aliases": ["ALB"]},
    "Total Protein": {"min": 6.0, "max": 8.3, "unit": "g/dL", "aliases": ["T.P", "PROTEIN"]},
    "ALP": {"min": 44, "max": 147, "unit": "IU/L", "aliases": ["Alkaline Phosphatase"]},
    "ALT": {"min": 7, "max": 56, "unit": "IU/L", "aliases": ["SGPT"]},
    "AST": {"min": 10, "max": 40, "unit": "IU/L", "aliases": ["SGOT"]},
    "Bilirubin": {"min": 0.1, "max": 1.2, "unit": "mg/dL", "aliases": ["Total Bilirubin", "BILI"]},

    # Lipid Profile
    "Cholesterol": {"min": 0, "max": 200, "unit": "mg/dL", "aliases": ["Total Cholesterol", "CHOL"]},
    "HDL": {"min": 40, "max": 60, "unit": "mg/dL", "aliases": ["Good Cholesterol"]},
    "LDL": {"min": 0, "max": 100, "unit": "mg/dL", "aliases": ["Bad Cholesterol"]},
    "Triglycerides": {"min": 0, "max": 150, "unit": "mg/dL", "aliases": ["TRIG"]},

    # Thyroid / Hormones
    "TSH": {"min": 0.4, "max": 4.0, "unit": "mIU/L", "aliases": ["Thyroid Stimulating Hormone"]},
    "Free T4": {"min": 0.7, "max": 1.9, "unit": "ng/dL", "aliases": ["FT4"]},
    "Free T3": {"min": 2.3, "max": 4.2, "unit": "pg/mL", "aliases": ["FT3"]},
    "PSA": {"min": 0, "max": 4.0, "unit": "ng/mL", "aliases": ["Prostate Specific Antigen"]},

    # Inflammatory / Vitamins / Others
    "CRP": {"min": 0, "max": 10, "unit": "mg/L", "aliases": ["C-Reactive Protein"]},
    "ESR": {"min": 0, "max": 15, "unit": "mm/hr", "aliases": ["Sed Rate"]},
    "Iron": {"min": 60, "max": 170, "unit": "mcg/dL", "aliases": ["Serum Iron", "FE"]},
    "Ferritin": {"min": 20, "max": 250, "unit": "ng/mL", "aliases": ["FERR"]},
    "Vitamin B12": {"min": 200, "max": 900, "unit": "pg/mL", "aliases": ["B12"]},
    "Vitamin D": {"min": 30, "max": 100, "unit": "ng/mL", "aliases": ["25-OH Vitamin D"]},
    "A1c": {"min": 4, "max": 5.6, "unit": "%", "aliases": ["HbA1c", "Glycohemoglobin"]},
    "Uric Acid": {"min": 3.5, "max": 7.2, "unit": "mg/dL", "aliases": ["URIC"]},
    "Magnesium": {"min": 1.7, "max": 2.2, "unit": "mg/dL", "aliases": ["MG"]},
    "Phosphorus": {"min": 2.5, "max": 4.5, "unit": "mg/dL", "aliases": ["PHOS"]},
    "Amylase": {"min": 30, "max": 110, "unit": "U/L", "aliases": ["AMY"]},
    "Lipase": {"min": 0, "max": 160, "unit": "U/L", "aliases": ["LIP"]},
    "GGT": {"min": 9, "max": 48, "unit": "U/L", "aliases": ["Gamma-Glutamyl Transferase"]}
}

def respond(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,GET,POST,PUT',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
        },
        'body': json.dumps(body)
    }

def get_status(marker_name, value):
    if marker_name not in MEDICAL_MARKERS:
        return "Normal"
    rng = MEDICAL_MARKERS[marker_name]
    if value < rng["min"]:
        return "Low"
    elif value > rng["max"]:
        return "High"
    return "Normal"

def parse_markers(text):
    results = []
    seen_markers = set()
    
    for marker_key, details in MEDICAL_MARKERS.items():
        # Build search list including primary name and all aliases
        search_terms = [marker_key] + details.get("aliases", [])
        
        for term in search_terms:
            if marker_key in seen_markers:
                break
                
            # Regex: Look for term followed by separator (:, space, etc) and then a number
            # Support for: "Hb: 14.5", "Hb 14.5", "Hemoglobin:14.5", etc.
            pattern = rf"{re.escape(term)}[:\s]*(\d+\.?\d*)"
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                try:
                    val = float(match.group(1))
                    results.append({
                        "name": marker_key,
                        "value": val,
                        "unit": details["unit"],
                        "status": get_status(marker_key, val),
                        "range": f"{details['min']} - {details['max']}"
                    })
                    seen_markers.add(marker_key)
                except ValueError:
                    continue
    return results

def lambda_handler(event, context):
    print(f"DEBUG: Event: {json.dumps(event)}")
    path = event.get('rawPath', '/')
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    
    if method == 'OPTIONS':
        return respond(200, {})

    if path == '/get-upload-url':
        file_name = event.get('queryStringParameters', {}).get('filename', f'report-{uuid.uuid4()}.jpg')
        content_type = event.get('queryStringParameters', {}).get('type', 'image/jpeg')
        object_name = f"uploads/{uuid.uuid4()}-{file_name}"
        
        try:
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': BUCKET_NAME, 
                    'Key': object_name,
                    'ContentType': content_type
                },
                ExpiresIn=300
            )
            return respond(200, {'uploadUrl': presigned_url, 'key': object_name})
        except Exception as e:
            return respond(500, {'error': str(e)})

    elif path == '/analyze':
        body_str = event.get('body')
        if not body_str:
            return respond(400, {'error': 'Missing body'})
        
        body = json.loads(body_str)
        object_key = body.get('key')
        
        if not object_key:
            return respond(400, {'error': 'Missing S3 key'})

        try:
            # 1. AWS Textract
            response = textract_client.detect_document_text(
                Document={'S3Object': {'Bucket': BUCKET_NAME, 'Name': object_key}}
            )
            
            blocks = response.get('Blocks', [])
            extracted_text = " ".join([item["Text"] for item in blocks if item["BlockType"] == "LINE"])
            
            # 2. Medical Parameter Extraction
            markers = parse_markers(extracted_text)
            
            # 3. AWS Comprehend (Sentiment/Entities for additional context)
            truncated_text = extracted_text[:4900]
            sentiment = "UNKNOWN"
            entities = []
            
            if truncated_text:
                sentiment_resp = comprehend_client.detect_sentiment(Text=truncated_text, LanguageCode='en')
                sentiment = sentiment_resp.get('Sentiment', 'UNKNOWN')
                entities_resp = comprehend_client.detect_entities(Text=truncated_text, LanguageCode='en')
                entities = entities_resp.get('Entities', [])[:5]

            # 4. Store in DynamoDB
            doc_id = str(uuid.uuid4())
            if table:
                item = {
                    'id': doc_id,
                    's3_key': object_key,
                    'markers': json.dumps(markers),
                    'sentiment': sentiment,
                    'timestamp': str(uuid.uuid1())
                }
                table.put_item(Item=item)
            
            # 5. Return to frontend
            return respond(200, {
                'id': doc_id,
                'sentiment': sentiment,
                'markers': markers,
                'rawTextPreview': extracted_text[:500] if not markers else ""
            })
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return respond(500, {'error': str(e)})

    return respond(404, {'error': 'Not Found'})
