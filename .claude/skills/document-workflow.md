# CogniSys Document Workflow Skill

## Purpose
Automate the complete document processing workflow: scan, extract, classify, organize, and track.

## Workflow Steps

### 1. Initial Assessment
- Check if the document exists in the CogniSys database
- Query for similar documents using `cognisys_query_documents`
- Review past classifications of similar files

### 2. Content Extraction
- Use `cognisys_classify_document` to process the file
- Extract text content, metadata, and entities
- Determine document structure (pages, sections, tables)

### 3. Classification
- Apply ML classifier to determine document type
- Show confidence score and reasoning
- If confidence < 70%, ask user for manual classification

### 4. Verification
- Present classification result to user
- Show key entities extracted (dates, names, amounts)
- Ask if classification is correct

### 5. Feedback Loop
- If classification is incorrect, use `cognisys_submit_feedback`
- Store feedback for model retraining
- Update document metadata

### 6. Organization
- Suggest target location based on document type
- Create necessary directory structure
- Move file to organized location
- Update database with new path

## Usage Example

```
User: Process this invoice document
Assistant:
1. Checking CogniSys database for existing classification...
2. Classifying via ML pipeline...
3. Result: financial_invoice (confidence: 85%)
4. Extracted entities: Invoice #12345, $1,250.00, Due: 2025-01-15
5. Is this classification correct? [yes/no]
User: yes
Assistant:
6. Moving to: Documents/Financial/Invoices/2025/01/invoice_12345.pdf
7. Updated database record #1234
```

## Available Tools
- `cognisys_query_documents` - Search existing documents
- `cognisys_classify_document` - Run ML classification
- `cognisys_submit_feedback` - Correct classifications
- `cognisys_get_categories` - List all document types
- `cognisys_get_classification_stats` - View statistics

## Best Practices
- Always verify high-value documents (financial, legal)
- Collect feedback on low-confidence classifications
- Batch process similar documents together
- Monitor classification accuracy trends
