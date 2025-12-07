"""
Flask API Server
REST API bridge for PowerShell to Python ML functionality
"""

import logging
from flask import Flask, request, jsonify
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cognisys.ml.ocr import GPUOCREngine, create_ocr_engine
from cognisys.ml.utils import ContentExtractor, create_extractor
from cognisys.ml.nlp import TextAnalyzer, create_analyzer
from cognisys.ml.classification import MLClassifier, create_classifier
from cognisys.ml.learning import TrainingDatabase, create_database
from cognisys.ml.api.security import configure_cors, apply_security_headers, rate_limit


# Initialize Flask app
app = Flask(__name__)

# Apply security middleware
configure_cors(app)  # Restrict CORS to localhost only
apply_security_headers(app)  # Add OWASP security headers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances (loaded on demand)
ocr_engine = None
content_extractor = None
text_analyzer = None
ml_classifier = None
training_db = None


def get_ocr_engine():
    """Get or create OCR engine instance."""
    global ocr_engine
    if ocr_engine is None:
        logger.info("Initializing OCR engine...")
        ocr_engine = create_ocr_engine(use_gpu=True)
    return ocr_engine


def get_content_extractor():
    """Get or create content extractor instance."""
    global content_extractor
    if content_extractor is None:
        logger.info("Initializing content extractor...")
        ocr = get_ocr_engine()
        content_extractor = create_extractor(ocr_engine=ocr)
    return content_extractor


def get_text_analyzer():
    """Get or create text analyzer instance."""
    global text_analyzer
    if text_analyzer is None:
        logger.info("Initializing text analyzer...")
        text_analyzer = create_analyzer(language_model="en_core_web_sm")
    return text_analyzer


def get_ml_classifier():
    """Get or create ML classifier instance."""
    global ml_classifier
    if ml_classifier is None:
        logger.info("Initializing ML classifier...")
        ml_classifier = create_classifier()
        # Try to load existing model
        ml_classifier.load_model()
    return ml_classifier


def get_training_db():
    """Get or create training database instance."""
    global training_db
    if training_db is None:
        logger.info("Initializing training database...")
        training_db = create_database()
    return training_db


# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Check API health and GPU status."""
    try:
        ocr = get_ocr_engine()
        gpu_info = ocr.get_gpu_info()

        return jsonify({
            'status': 'healthy',
            'version': '1.0.0',
            'gpu_available': gpu_info.get('gpu_available', False),
            'gpu_name': gpu_info.get('device_name', 'N/A')
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# OCR endpoints
@app.route('/ocr/extract', methods=['POST'])
@rate_limit
def ocr_extract():
    """Extract text from a single image or PDF page."""
    try:
        data = request.get_json()
        image_path = data.get('image_path')

        if not image_path:
            return jsonify({'error': 'image_path required'}), 400

        ocr = get_ocr_engine()
        result = ocr.extract_text(image_path)

        return jsonify(result)

    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return jsonify({'error': str(e)}), 500


# Content extraction endpoints
@app.route('/extract/document', methods=['POST'])
@rate_limit
def extract_document():
    """Extract content from any document type."""
    try:
        data = request.get_json()
        file_path = data.get('file_path')

        if not file_path:
            return jsonify({'error': 'file_path required'}), 400

        extractor = get_content_extractor()
        result = extractor.extract_content(file_path)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Document extraction failed: {e}")
        return jsonify({'error': str(e)}), 500


# Text analysis endpoints
@app.route('/analyze/text', methods=['POST'])
def analyze_text():
    """Analyze text and extract entities, keywords, features."""
    try:
        data = request.get_json()
        text = data.get('text')

        if not text:
            return jsonify({'error': 'text required'}), 400

        analyzer = get_text_analyzer()
        result = analyzer.analyze_text(text)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Text analysis failed: {e}")
        return jsonify({'error': str(e)}), 500


# Classification endpoints
@app.route('/classify/document', methods=['POST'])
def classify_document():
    """Classify a document using ML model."""
    try:
        data = request.get_json()
        document = data.get('document')  # Expects full document dict with extraction + analysis

        if not document:
            return jsonify({'error': 'document required'}), 400

        classifier = get_ml_classifier()
        result = classifier.predict(document)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return jsonify({'error': str(e)}), 500


# End-to-end pipeline endpoint
@app.route('/process/document', methods=['POST'])
@rate_limit  # Apply rate limiting to prevent abuse
def process_document():
    """
    Complete document processing pipeline:
    1. Extract content (OCR if needed)
    2. Analyze text
    3. Classify with ML
    4. Store in database
    """
    try:
        data = request.get_json()
        file_path = data.get('file_path')

        if not file_path:
            return jsonify({'error': 'file_path required'}), 400

        # Step 1: Extract content
        extractor = get_content_extractor()
        extraction = extractor.extract_content(file_path)

        if not extraction['success']:
            return jsonify({
                'success': False,
                'error': 'Content extraction failed',
                'details': extraction
            }), 500

        # Step 2: Analyze text (pass filename for better classification)
        analyzer = get_text_analyzer()
        import os
        filename = os.path.basename(file_path)
        analysis = analyzer.analyze_text(extraction['text'], filename=filename)

        # Step 3: Classify
        classifier = get_ml_classifier()
        document = {
            'extraction': extraction,
            'analysis': analysis
        }
        prediction = classifier.predict(document)

        # Step 4: Store in database
        db = get_training_db()
        doc_id = db.add_document(file_path, extraction, analysis)

        if prediction.get('success'):
            pred_id = db.add_prediction(doc_id, prediction)
        else:
            pred_id = None

        # Return complete results
        return jsonify({
            'success': True,
            'file_path': file_path,
            'document_id': doc_id,
            'prediction_id': pred_id,
            'extraction': extraction,
            'analysis': analysis,
            'prediction': prediction
        })

    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Feedback endpoints
@app.route('/feedback/submit', methods=['POST'])
def submit_feedback():
    """Submit user feedback for a classification."""
    try:
        data = request.get_json()
        document_id = data.get('document_id')
        correct_category = data.get('correct_category')
        prediction_id = data.get('prediction_id')
        was_correct = data.get('was_correct', False)
        comment = data.get('comment')

        if not document_id or not correct_category:
            return jsonify({'error': 'document_id and correct_category required'}), 400

        db = get_training_db()
        feedback_id = db.add_feedback(
            document_id=document_id,
            correct_category=correct_category,
            prediction_id=prediction_id,
            was_correct=was_correct,
            user_comment=comment
        )

        return jsonify({
            'success': True,
            'feedback_id': feedback_id,
            'message': 'Feedback recorded successfully'
        })

    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        return jsonify({'error': str(e)}), 500


# Training endpoints
@app.route('/training/start', methods=['POST'])
def start_training():
    """Train or retrain the ML model using database feedback."""
    try:
        data = request.get_json()
        model_version = data.get('model_version', 'v1.0')

        # Get training data from database
        db = get_training_db()
        training_samples = db.get_training_data(min_confidence=0.5, include_feedback=True)

        if len(training_samples) < 10:
            return jsonify({
                'success': False,
                'error': f'Insufficient training data ({len(training_samples)} samples, need at least 10)'
            }), 400

        # TODO: Load full document data for training
        # For now, return info about available data
        return jsonify({
            'success': True,
            'message': 'Training data ready',
            'training_samples': len(training_samples),
            'note': 'Full training pipeline requires document reloading'
        })

    except Exception as e:
        logger.error(f"Training failed: {e}")
        return jsonify({'error': str(e)}), 500


# Database statistics
@app.route('/stats', methods=['GET'])
def get_statistics():
    """Get system statistics."""
    try:
        db = get_training_db()
        stats = db.get_statistics()

        return jsonify({
            'success': True,
            'statistics': stats
        })

    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
        return jsonify({'error': str(e)}), 500


# Category management
@app.route('/categories', methods=['GET', 'POST'])
def manage_categories():
    """Get or add categories."""
    try:
        db = get_training_db()

        if request.method == 'GET':
            categories = db.get_categories()
            return jsonify({
                'success': True,
                'categories': categories
            })

        elif request.method == 'POST':
            data = request.get_json()
            category_name = data.get('category_name')
            description = data.get('description')
            pattern_path = data.get('pattern_path')

            if not category_name:
                return jsonify({'error': 'category_name required'}), 400

            cat_id = db.add_category(category_name, description, pattern_path)

            return jsonify({
                'success': True,
                'category_id': cat_id,
                'category_name': category_name
            })

    except Exception as e:
        logger.error(f"Category management failed: {e}")
        return jsonify({'error': str(e)}), 500


# Shutdown endpoint (for graceful shutdown)
@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the API server."""
    logger.info("Shutdown requested")

    # Close database connection
    global training_db
    if training_db:
        training_db.close()

    return jsonify({'message': 'Server shutting down'})


if __name__ == '__main__':
    logger.info("Starting IFMOS ML API Server...")
    logger.info("Endpoints:")
    logger.info("  GET  /health - Health check")
    logger.info("  POST /process/document - Full document processing pipeline")
    logger.info("  POST /extract/document - Extract content only")
    logger.info("  POST /analyze/text - Analyze text only")
    logger.info("  POST /classify/document - Classify document only")
    logger.info("  POST /feedback/submit - Submit classification feedback")
    logger.info("  GET  /stats - Get system statistics")
    logger.info("  GET  /categories - List categories")

    # Run server
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,  # Disable debug in production
        threaded=True
    )
