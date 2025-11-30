# NVIDIA Vision Integration Guide

## Overview
IFMOS now supports NVIDIA vision models for content-based classification of images and PDFs.

## Setup

### 1. Get NVIDIA API Key
1. Visit [https://build.nvidia.com](https://build.nvidia.com)
2. Create account or sign in
3. Navigate to API Keys section
4. Generate new API key

### 2. Configure Environment
```bash
# Set environment variable (Windows)
setx NVIDIA_API_KEY "your-api-key-here"

# Or add to .env file
echo NVIDIA_API_KEY=your-api-key-here >> .env
```

### 3. Install Dependencies
```bash
pip install requests Pillow pdf2image
```

## Usage

### Standalone Testing
```python
from ifmos.ml.vision import NVIDIAVisionClassifier

# Initialize
classifier = NVIDIAVisionClassifier()

# Classify an image
doc_type, confidence, method = classifier.classify_image(Path("screenshot.png"))
print(f"{doc_type} ({confidence:.2f})")
```

### Integration with IFMOS Classification
```python
# In reclassify_null_files.py or similar
from ifmos.ml.vision import NVIDIAVisionClassifier

# Initialize vision classifier
vision_classifier = NVIDIAVisionClassifier()

def enhanced_classify(filename, file_path):
    # Try pattern-based first
    doc_type, conf, method = classify_with_patterns(filename)
    if doc_type:
        return doc_type, conf, method

    # For images/PDFs, try vision classification
    if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.pdf']:
        doc_type, conf, method = vision_classifier.classify_image(file_path)
        if doc_type:
            return doc_type, conf, method

    # Fall back to ML
    return classify_with_ml(filename)
```

## Supported File Types
- **Images**: .png, .jpg, .jpeg, .gif, .bmp, .webp
- **PDFs**: .pdf (renders first page)

## Classification Categories

### Enhanced Categories
- `media_screenshot_code` - Screenshots of code/terminal
- `media_screenshot_dataviz` - Charts, graphs, visualizations
- `financial_invoice` - Invoices, receipts, bills
- `design_diagram` - Technical diagrams, schematics
- `media_screenshot` - General application screenshots
- `media_image` - Photos, pictures
- `scanned_document` - Scanned text documents

## Cost Estimation

### NVIDIA NIM Pricing (Approximate)
- Vision API: ~$0.01-0.05 per call
- Recommended: Use only for ambiguous files (no pattern match)

### For IFMOS Database (104k files)
- Images: ~800 files
- PDFs: ~6,663 files
- **Estimated calls**: 1,500-2,000 (filtering out pattern-matched)
- **Estimated cost**: $15-100 one-time

## Performance Optimization

### Caching Strategy
```python
# Cache vision results in database
def classify_with_vision_cached(file_path):
    # Check cache first
    cached_result = db.get_vision_result(file_path.name)
    if cached_result:
        return cached_result

    # Call NVIDIA API
    result = vision_classifier.classify_image(file_path)

    # Cache result
    db.save_vision_result(file_path.name, result)

    return result
```

### Batch Processing
Process images in batches to manage API rate limits:
- Batch size: 10-50 files
- Delay between batches: 1-2 seconds
- Total processing time: ~30-60 minutes for full database

## Testing

### Quick Test
```bash
python -m ifmos.ml.vision.nvidia_vision
```

### Full Integration Test
```python
from pathlib import Path
from ifmos.ml.vision import NVIDIAVisionClassifier

classifier = NVIDIAVisionClassifier()

test_files = [
    "sample_code_screenshot.png",
    "sample_invoice.pdf",
    "sample_chart.png"
]

for test_file in test_files:
    doc_type, conf, method = classifier.classify_image(Path(test_file))
    print(f"{test_file}: {doc_type} ({conf:.2f})")
```

## Next Steps

1. **Obtain API Key**: Get NVIDIA API key from build.nvidia.com
2. **Test Integration**: Test on 10-20 sample files
3. **Measure Accuracy**: Compare vision results vs pattern/ML
4. **Full Deployment**: Process all images/PDFs in database
5. **Monitor Costs**: Track API usage and costs

## Expected Improvements
- **PDFs**: 60% → 85% accuracy (+25%)
- **Images**: 40% → 75% accuracy (+35%)
- **Overall**: 92.8% → 96%+ with vision enhancement

---

**Status**: ✅ Module created, ready for API key integration
**Next**: Obtain NVIDIA API key and test on sample files
