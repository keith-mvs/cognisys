"""
Synthetic Training Data Generator for CogniSys
Generates realistic document files for all 37 categories to address class imbalance.
"""

import random
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import csv


class SyntheticDataGenerator:
    """
    Generate synthetic training documents for ML classifier training.
    Creates realistic file content for each document category.
    """

    def __init__(self, output_dir: str = "synthetic_data", csv_output: str = "synthetic_training_data.csv"):
        self.output_dir = Path(output_dir)
        self.csv_output = csv_output
        self.output_dir.mkdir(exist_ok=True)

        # Document categories from ensemble model
        self.categories = [
            "archive", "automotive_technical", "backup_versioned", "business_presentation",
            "business_spreadsheet", "cache_package_manager", "compiled_code", "contact_vcard",
            "dependency_python", "design_cad", "design_document", "design_logo",
            "design_vector", "financial_document", "game_data", "git_metadata",
            "legal_document", "media_audio", "media_graphic", "media_photo",
            "media_screenshot", "personal_career", "personal_document", "personal_health",
            "software_installer", "source_header", "technical_config", "technical_database",
            "technical_dataset", "technical_documentation", "technical_log", "technical_manual",
            "technical_script", "web_bookmark", "web_font", "web_page", "web_stylesheet"
        ]

        # Templates for each category
        self.templates = self._build_templates()

        # File extensions for each category
        self.extensions = self._build_extensions()

    def _build_extensions(self) -> Dict[str, List[str]]:
        """Map categories to appropriate file extensions."""
        return {
            "archive": [".zip", ".tar", ".gz", ".7z", ".rar"],
            "automotive_technical": [".pdf", ".docx", ".txt"],
            "backup_versioned": [".bak", ".backup", ".old"],
            "business_presentation": [".pptx", ".ppt", ".pdf"],
            "business_spreadsheet": [".xlsx", ".xls", ".csv"],
            "cache_package_manager": [".cache", ".npm", ".pyc"],
            "compiled_code": [".dll", ".so", ".exe", ".o"],
            "contact_vcard": [".vcf", ".vcard"],
            "dependency_python": [".txt", ".lock"],
            "design_cad": [".dwg", ".dxf", ".step"],
            "design_document": [".ai", ".psd", ".sketch"],
            "design_logo": [".svg", ".ai", ".eps"],
            "design_vector": [".svg", ".eps", ".ai"],
            "financial_document": [".pdf", ".xlsx", ".docx"],
            "game_data": [".sav", ".dat", ".ini"],
            "git_metadata": [".git", ".gitignore", ".gitattributes"],
            "legal_document": [".pdf", ".docx", ".txt"],
            "media_audio": [".mp3", ".wav", ".flac"],
            "media_graphic": [".png", ".jpg", ".gif"],
            "media_photo": [".jpg", ".jpeg", ".raw"],
            "media_screenshot": [".png", ".jpg"],
            "personal_career": [".pdf", ".docx", ".txt"],
            "personal_document": [".docx", ".pdf", ".txt"],
            "personal_health": [".pdf", ".docx"],
            "software_installer": [".msi", ".exe", ".dmg"],
            "source_header": [".h", ".hpp", ".hxx"],
            "technical_config": [".json", ".yaml", ".ini", ".conf"],
            "technical_database": [".db", ".sqlite", ".mdb"],
            "technical_dataset": [".csv", ".json", ".parquet"],
            "technical_documentation": [".md", ".rst", ".txt"],
            "technical_log": [".log", ".txt"],
            "technical_manual": [".pdf", ".docx", ".html"],
            "technical_script": [".py", ".js", ".sh", ".ps1"],
            "web_bookmark": [".html", ".json"],
            "web_font": [".ttf", ".woff", ".woff2"],
            "web_page": [".html", ".htm"],
            "web_stylesheet": [".css", ".scss", ".less"]
        }

    def _build_templates(self) -> Dict[str, List[str]]:
        """Build content templates for each category."""
        return {
            "technical_script": [
                "#!/usr/bin/env python3\nimport sys\nimport os\nfrom pathlib import Path\n\ndef main():\n    \"\"\"Main entry point.\"\"\"\n    parser = argparse.ArgumentParser(description='{desc}')\n    args = parser.parse_args()\n    process_data(args)\n\nif __name__ == '__main__':\n    main()",
                "const fs = require('fs');\nconst path = require('path');\n\nfunction processFile(filePath) {{\n    const data = fs.readFileSync(filePath, 'utf8');\n    return data.split('\\n').filter(line => line.length > 0);\n}}\n\nmodule.exports = {{ processFile }};"
            ],
            "source_header": [
                "#ifndef {name}_H\n#define {name}_H\n\n#include <stdio.h>\n#include <stdlib.h>\n\ntypedef struct {{\n    int id;\n    char name[256];\n    double value;\n}} {name}_t;\n\nint {name}_init({name}_t *obj);\nvoid {name}_destroy({name}_t *obj);\n\n#endif",
                "#pragma once\n\n#include <vector>\n#include <string>\n\nnamespace {name} {{\n    class {class_name} {{\n    public:\n        {class_name}();\n        ~{class_name}();\n        void process();\n    private:\n        std::vector<int> data_;\n    }};\n}}"
            ],
            "technical_config": [
                "{{\n  \"version\": \"1.0.0\",\n  \"name\": \"{name}\",\n  \"settings\": {{\n    \"enabled\": true,\n    \"max_connections\": 100,\n    \"timeout\": 30,\n    \"log_level\": \"info\"\n  }}\n}}",
                "# Configuration file\nversion: 1.0\nname: {name}\n\nsettings:\n  enabled: true\n  max_threads: 8\n  buffer_size: 4096\n  \nlogging:\n  level: info\n  file: /var/log/{name}.log"
            ],
            "technical_documentation": [
                "# {title}\n\n## Overview\n\nThis document provides technical documentation for {name}.\n\n## Features\n\n- Feature 1: High performance processing\n- Feature 2: Scalable architecture\n- Feature 3: Comprehensive API\n\n## Installation\n\n```bash\npip install {name}\n```\n\n## Usage\n\n```python\nimport {name}\n\nresult = {name}.process(data)\n```\n\n## API Reference\n\nSee the API documentation for detailed information.",
                "= {title}\n\n== Introduction\n\nTechnical documentation for {name} system.\n\n== Architecture\n\nThe system consists of three main components:\n\n1. Data ingestion layer\n2. Processing engine\n3. Output formatter\n\n== Configuration\n\nConfiguration is managed through YAML files."
            ],
            "technical_log": [
                "[{timestamp}] INFO: Application started\n[{timestamp}] INFO: Loading configuration from config.yaml\n[{timestamp}] INFO: Connected to database\n[{timestamp}] DEBUG: Processing batch 1 of 100\n[{timestamp}] DEBUG: Processed 1000 records\n[{timestamp}] WARNING: High memory usage detected: 85%\n[{timestamp}] INFO: Batch complete\n[{timestamp}] ERROR: Connection timeout after 30s\n[{timestamp}] INFO: Retrying connection...\n[{timestamp}] INFO: Application shutdown",
                "{timestamp} [INFO] Server starting on port 8080\n{timestamp} [INFO] Database connection pool initialized (size=10)\n{timestamp} [DEBUG] Loading routes from routes.py\n{timestamp} [INFO] Registered 25 endpoints\n{timestamp} [INFO] Server ready to accept connections\n{timestamp} [INFO] Received request: GET /api/users\n{timestamp} [DEBUG] Query executed in 15ms\n{timestamp} [INFO] Response: 200 OK (23ms)"
            ],
            "business_spreadsheet": [
                "Invoice Number,Date,Customer,Amount,Tax,Total\nINV-001,2024-01-15,Acme Corp,5000.00,500.00,5500.00\nINV-002,2024-01-16,Tech Solutions,3200.00,320.00,3520.00\nINV-003,2024-01-17,Global Industries,7800.00,780.00,8580.00",
                "Month,Revenue,Expenses,Profit,Margin\nJan,125000,98000,27000,21.6%\nFeb,132000,102000,30000,22.7%\nMar,145000,108000,37000,25.5%"
            ],
            "financial_document": [
                "INVOICE\n\nInvoice Number: {invoice_num}\nDate: {date}\n\nBill To:\n{company}\n{address}\n\nDescription                Qty    Price    Total\n{item}                      1    ${amount}   ${amount}\n\nSubtotal:                         ${amount}\nTax (10%):                        ${tax}\nTotal:                            ${total}\n\nPayment Terms: Net 30\nDue Date: {due_date}",
                "FINANCIAL STATEMENT\n\nPeriod: Q4 2024\nCompany: {company}\n\nRevenue:              ${revenue}\nCost of Goods Sold:   ${cogs}\nGross Profit:         ${gross}\n\nOperating Expenses:\n  Salaries:           ${salaries}\n  Rent:               ${rent}\n  Utilities:          ${utilities}\n\nNet Income:           ${net}"
            ],
            "legal_document": [
                "AGREEMENT\n\nThis Agreement is entered into on {date} between:\n\nParty A: {party_a}\nParty B: {party_b}\n\nWHEREAS, the parties wish to establish terms for {purpose};\n\nNOW, THEREFORE, in consideration of the mutual covenants contained herein:\n\n1. Term: This agreement shall commence on {start_date} and continue for a period of {duration}.\n\n2. Obligations: Party A agrees to {obligation_a}. Party B agrees to {obligation_b}.\n\n3. Compensation: Payment of ${amount} shall be made according to the following schedule: {schedule}.\n\n4. Termination: Either party may terminate with {notice_period} written notice.\n\nIN WITNESS WHEREOF, the parties have executed this Agreement.\n\n__________________          __________________\nParty A                      Party B",
                "TERMS AND CONDITIONS\n\nLast Updated: {date}\n\n1. ACCEPTANCE OF TERMS\n\nBy accessing and using this service, you accept and agree to be bound by these Terms and Conditions.\n\n2. USE LICENSE\n\nPermission is granted to temporarily access the service for personal, non-commercial use only.\n\n3. DISCLAIMER\n\nThe service is provided \"as is\" without warranty of any kind.\n\n4. LIMITATIONS\n\nIn no event shall {company} be liable for any damages arising out of the use or inability to use the service.\n\n5. GOVERNING LAW\n\nThese terms shall be governed by the laws of {jurisdiction}."
            ],
            "personal_career": [
                "{name}\n{email} | {phone} | {location}\n\nPROFESSIONAL SUMMARY\n\nExperienced {title} with {years} years in {industry}. Proven track record in {skill_1}, {skill_2}, and {skill_3}.\n\nEXPERIENCE\n\n{title} | {company} | {start_date} - {end_date}\n• {achievement_1}\n• {achievement_2}\n• {achievement_3}\n\n{prev_title} | {prev_company} | {prev_start} - {prev_end}\n• {prev_achievement_1}\n• {prev_achievement_2}\n\nEDUCATION\n\n{degree} in {field} | {university} | {grad_year}\n\nSKILLS\n\n{skill_1} • {skill_2} • {skill_3} • {skill_4}",
                "COVER LETTER\n\n{date}\n\n{hiring_manager}\n{company}\n{address}\n\nDear {hiring_manager},\n\nI am writing to express my strong interest in the {position} position at {company}. With {years} years of experience in {field}, I am confident in my ability to contribute to your team.\n\nIn my current role at {current_company}, I have {achievement}. This experience has prepared me to {skill_application}.\n\nI am particularly drawn to {company} because of {reason}. I am excited about the opportunity to {contribution}.\n\nThank you for your consideration. I look forward to discussing how my background aligns with your needs.\n\nSincerely,\n{name}"
            ],
            "personal_document": [
                "PERSONAL JOURNAL ENTRY\n\nDate: {date}\n\nToday was {mood}. I spent time {activity_1} and {activity_2}. \n\nThoughts on {topic}: {reflection}\n\nGoals for tomorrow:\n- {goal_1}\n- {goal_2}\n- {goal_3}",
                "NOTES: {topic}\n\n{date}\n\nKey Points:\n• {point_1}\n• {point_2}\n• {point_3}\n\nAction Items:\n□ {action_1}\n□ {action_2}\n\nReminders:\n- {reminder_1}\n- {reminder_2}"
            ],
            "personal_health": [
                "MEDICAL RECORD\n\nPatient: {name}\nDate of Birth: {dob}\nVisit Date: {date}\n\nChief Complaint: {complaint}\n\nVital Signs:\n  Blood Pressure: {bp}\n  Heart Rate: {hr} bpm\n  Temperature: {temp}°F\n  Weight: {weight} lbs\n\nAssessment: {assessment}\n\nPlan:\n- {plan_1}\n- {plan_2}\n- Follow-up in {followup}\n\nPhysician: Dr. {doctor}",
                "VACCINATION RECORD\n\nPatient Name: {name}\nDate of Birth: {dob}\n\nVaccination History:\n\n{vaccine_1} - {date_1} - Lot: {lot_1}\n{vaccine_2} - {date_2} - Lot: {lot_2}\n{vaccine_3} - {date_3} - Lot: {lot_3}\n\nNext Due: {next_vaccine} on {next_date}\n\nHealthcare Provider: {provider}"
            ],
            "technical_manual": [
                "{product} User Manual\n\nVersion {version}\n\nTable of Contents\n1. Introduction\n2. Installation\n3. Configuration\n4. Operation\n5. Troubleshooting\n6. Maintenance\n\n1. INTRODUCTION\n\nThank you for choosing {product}. This manual provides instructions for installation, operation, and maintenance.\n\n2. INSTALLATION\n\nSystem Requirements:\n- Operating System: {os}\n- RAM: {ram} GB\n- Disk Space: {disk} GB\n\nInstallation Steps:\n1. Download installer from {url}\n2. Run setup executable\n3. Follow on-screen instructions\n4. Restart system\n\n3. CONFIGURATION\n\nConfiguration files are located in {config_path}.",
                "TECHNICAL SPECIFICATIONS\n\nProduct: {product}\nModel: {model}\nManufacturer: {manufacturer}\n\nPHYSICAL CHARACTERISTICS\n- Dimensions: {dimensions}\n- Weight: {weight}\n- Material: {material}\n\nPERFORMANCE\n- Max Speed: {speed}\n- Power: {power}\n- Efficiency: {efficiency}%\n\nOPERATING CONDITIONS\n- Temperature: {temp_range}\n- Humidity: {humidity_range}\n- Voltage: {voltage}\n\nMAINTENANCE SCHEDULE\n- Daily: {daily_maint}\n- Weekly: {weekly_maint}\n- Monthly: {monthly_maint}"
            ],
            "web_page": [
                "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>{title}</title>\n    <link rel=\"stylesheet\" href=\"styles.css\">\n</head>\n<body>\n    <header>\n        <h1>{heading}</h1>\n        <nav>\n            <a href=\"#home\">Home</a>\n            <a href=\"#about\">About</a>\n            <a href=\"#contact\">Contact</a>\n        </nav>\n    </header>\n    <main>\n        <section>\n            <h2>{section_title}</h2>\n            <p>{content}</p>\n        </section>\n    </main>\n    <footer>\n        <p>&copy; 2024 {company}. All rights reserved.</p>\n    </footer>\n</body>\n</html>",
                "<html>\n<head><title>{title}</title></head>\n<body>\n<h1>{heading}</h1>\n<div class=\"content\">\n<p>{paragraph_1}</p>\n<p>{paragraph_2}</p>\n</div>\n<div class=\"sidebar\">\n<h3>Quick Links</h3>\n<ul>\n<li><a href=\"{link_1}\">{link_1_text}</a></li>\n<li><a href=\"{link_2}\">{link_2_text}</a></li>\n</ul>\n</div>\n</body>\n</html>"
            ],
            "web_stylesheet": [
                "/* {name} Stylesheet */\n\n:root {{\n    --primary-color: {color_1};\n    --secondary-color: {color_2};\n    --font-family: {font};\n}}\n\n* {{\n    margin: 0;\n    padding: 0;\n    box-sizing: border-box;\n}}\n\nbody {{\n    font-family: var(--font-family);\n    line-height: 1.6;\n    color: #333;\n}}\n\n.container {{\n    max-width: 1200px;\n    margin: 0 auto;\n    padding: 20px;\n}}\n\n.header {{\n    background: var(--primary-color);\n    color: white;\n    padding: 20px;\n}}\n\n.btn {{\n    background: var(--primary-color);\n    color: white;\n    padding: 10px 20px;\n    border: none;\n    border-radius: 4px;\n    cursor: pointer;\n}}",
                ".nav {{\n    display: flex;\n    justify-content: space-between;\n    align-items: center;\n    background-color: {bg_color};\n    padding: 1rem 2rem;\n}}\n\n.nav-link {{\n    color: {link_color};\n    text-decoration: none;\n    margin: 0 1rem;\n    font-weight: 500;\n}}\n\n.nav-link:hover {{\n    color: {hover_color};\n    border-bottom: 2px solid {hover_color};\n}}\n\n@media (max-width: 768px) {{\n    .nav {{\n        flex-direction: column;\n    }}\n}}"
            ],
            "technical_dataset": [
                "id,name,category,value,timestamp\n1,sample_001,type_a,123.45,2024-01-15T10:30:00\n2,sample_002,type_b,234.56,2024-01-15T10:31:00\n3,sample_003,type_a,345.67,2024-01-15T10:32:00\n4,sample_004,type_c,456.78,2024-01-15T10:33:00",
                "{{\n  \"dataset\": \"{name}\",\n  \"version\": \"1.0\",\n  \"records\": [\n    {{\"id\": 1, \"value\": {val_1}, \"label\": \"{label_1}\"}},\n    {{\"id\": 2, \"value\": {val_2}, \"label\": \"{label_2}\"}},\n    {{\"id\": 3, \"value\": {val_3}, \"label\": \"{label_3}\"}}\n  ]\n}}"
            ]
        }

    def _generate_timestamp(self, days_ago: int = 0) -> str:
        """Generate timestamp for logs."""
        dt = datetime.now() - timedelta(days=days_ago)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _fill_template(self, template: str, category: str) -> str:
        """Fill template with randomized values."""
        # Common replacement values
        replacements = {
            'name': random.choice(['processor', 'handler', 'manager', 'service', 'controller', 'analyzer']),
            'class_name': random.choice(['DataProcessor', 'FileHandler', 'ServiceManager', 'RequestController']),
            'title': random.choice(['System Overview', 'API Guide', 'User Manual', 'Technical Specification']),
            'desc': random.choice(['Process data files', 'Handle user requests', 'Manage system resources']),
            'company': random.choice(['Acme Corp', 'Tech Solutions', 'Global Industries', 'Digital Systems']),
            'address': f"{random.randint(100, 9999)} Main St, City, ST {random.randint(10000, 99999)}",
            'date': (datetime.now() - timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
            'timestamp': self._generate_timestamp(days_ago=random.randint(0, 30)),
            'invoice_num': f"INV-{random.randint(1000, 9999)}",
            'amount': f"{random.randint(1000, 10000):.2f}",
            'tax': f"{random.randint(100, 1000):.2f}",
            'total': f"{random.randint(1100, 11000):.2f}",
            'revenue': f"{random.randint(50000, 200000)}",
            'cogs': f"{random.randint(30000, 150000)}",
            'gross': f"{random.randint(20000, 50000)}",
            'salaries': f"{random.randint(10000, 30000)}",
            'rent': f"{random.randint(2000, 5000)}",
            'utilities': f"{random.randint(500, 2000)}",
            'net': f"{random.randint(5000, 20000)}",
            'email': f"user{random.randint(1, 999)}@example.com",
            'phone': f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            'location': random.choice(['New York, NY', 'San Francisco, CA', 'Chicago, IL', 'Austin, TX']),
            'years': random.randint(3, 15),
            'position': random.choice(['Software Engineer', 'Data Scientist', 'Product Manager', 'DevOps Engineer']),
            'industry': random.choice(['technology', 'finance', 'healthcare', 'e-commerce']),
            'skill_1': random.choice(['Python', 'Java', 'JavaScript', 'Go']),
            'skill_2': random.choice(['AWS', 'Docker', 'Kubernetes', 'Azure']),
            'skill_3': random.choice(['ML', 'Data Analysis', 'System Design', 'API Development']),
            'skill_4': random.choice(['CI/CD', 'Testing', 'Security', 'Performance']),
            'color_1': random.choice(['#007bff', '#28a745', '#dc3545', '#ffc107']),
            'color_2': random.choice(['#6c757d', '#17a2b8', '#343a40', '#f8f9fa']),
            'font': random.choice(['Arial, sans-serif', 'Georgia, serif', 'Courier, monospace']),
            'bg_color': random.choice(['#333', '#2c3e50', '#34495e']),
            'link_color': random.choice(['#fff', '#ecf0f1', '#bdc3c7']),
            'hover_color': random.choice(['#ff6b6b', '#4ecdc4', '#45b7d1']),
            'val_1': random.randint(100, 999),
            'val_2': random.randint(100, 999),
            'val_3': random.randint(100, 999),
            'label_1': f"label_{random.randint(1, 10)}",
            'label_2': f"label_{random.randint(1, 10)}",
            'label_3': f"label_{random.randint(1, 10)}",
            'party_a': random.choice(['Acme Corporation', 'Tech Solutions Inc', 'Global Industries LLC']),
            'party_b': random.choice(['Digital Systems', 'Innovation Labs', 'Future Tech Co']),
            'purpose': random.choice(['software development', 'consulting services', 'product licensing']),
            'start_date': (datetime.now() - timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d"),
            'duration': random.choice(['12 months', '24 months', '36 months']),
            'obligation_a': random.choice(['deliver software', 'provide services', 'license technology']),
            'obligation_b': random.choice(['pay fees', 'provide resources', 'maintain confidentiality']),
            'notice_period': random.choice(['30 days', '60 days', '90 days']),
            'schedule': random.choice(['monthly', 'quarterly', 'upon delivery']),
            'jurisdiction': random.choice(['California', 'New York', 'Delaware']),
            'due_date': (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            'hiring_manager': random.choice(['John Smith', 'Jane Doe', 'Robert Johnson']),
            'current_company': random.choice(['Tech Corp', 'Software Inc', 'Digital Solutions']),
            'field': random.choice(['Computer Science', 'Software Engineering', 'Data Science']),
            'university': random.choice(['State University', 'Tech Institute', 'College of Engineering']),
            'grad_year': random.randint(2010, 2022),
            'achievement': random.choice(['increased efficiency by 30%', 'led team of 5 engineers', 'launched major product']),
            'achievement_1': random.choice(['Developed scalable microservices', 'Implemented CI/CD pipeline', 'Reduced latency by 40%']),
            'achievement_2': random.choice(['Mentored junior developers', 'Designed system architecture', 'Optimized database queries']),
            'achievement_3': random.choice(['Led code reviews', 'Implemented testing framework', 'Deployed to production']),
            'prev_title': random.choice(['Junior Engineer', 'Associate Developer', 'Software Developer']),
            'prev_company': random.choice(['StartUp Inc', 'Tech Ventures', 'Code Solutions']),
            'prev_start': '2018-01',
            'prev_end': '2020-12',
            'prev_achievement_1': 'Built web applications',
            'prev_achievement_2': 'Collaborated with team',
            'degree': random.choice(['Bachelor of Science', 'Master of Science', 'PhD']),
            'skill_application': 'contribute effectively to your team',
            'reason': 'your innovative approach to technology',
            'contribution': 'help drive your mission forward',
            'dob': f"{random.randint(1960, 2000)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
            'complaint': random.choice(['headache', 'fever', 'routine checkup']),
            'bp': f"{random.randint(110, 130)}/{random.randint(70, 85)}",
            'hr': random.randint(60, 90),
            'temp': round(random.uniform(97.5, 99.0), 1),
            'weight': random.randint(120, 200),
            'assessment': random.choice(['Patient appears healthy', 'Mild symptoms observed', 'Follow-up recommended']),
            'plan_1': 'Continue current treatment',
            'plan_2': 'Schedule follow-up appointment',
            'followup': random.choice(['1 week', '2 weeks', '1 month']),
            'doctor': random.choice(['Smith', 'Johnson', 'Williams', 'Brown']),
            'vaccine_1': 'Influenza',
            'vaccine_2': 'Tetanus',
            'vaccine_3': 'COVID-19',
            'date_1': '2022-10-15',
            'date_2': '2021-05-20',
            'date_3': '2023-01-10',
            'lot_1': f"LOT{random.randint(10000, 99999)}",
            'lot_2': f"LOT{random.randint(10000, 99999)}",
            'lot_3': f"LOT{random.randint(10000, 99999)}",
            'next_vaccine': 'Influenza',
            'next_date': (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d"),
            'provider': random.choice(['City Medical', 'Health Center', 'Clinic Plus']),
            'product': random.choice(['System X', 'Device Pro', 'Platform 2000']),
            'version': f"{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
            'model': f"MODEL-{random.randint(100, 999)}",
            'manufacturer': random.choice(['TechCorp', 'IndustrialSys', 'ManufacturePro']),
            'os': random.choice(['Windows 10+', 'macOS 11+', 'Linux Ubuntu 20.04+']),
            'ram': random.choice([4, 8, 16, 32]),
            'disk': random.choice([10, 20, 50, 100]),
            'config_path': random.choice(['/etc/app/', 'C:\\Program Files\\App\\', '/opt/app/']),
            'url': 'https://example.com/download',
            'dimensions': f"{random.randint(10, 50)}x{random.randint(10, 50)}x{random.randint(10, 50)} cm",
            'weight': f"{random.randint(5, 50)} kg",
            'material': random.choice(['Steel', 'Aluminum', 'Plastic']),
            'speed': f"{random.randint(100, 1000)} rpm",
            'power': f"{random.randint(100, 5000)} W",
            'efficiency': random.randint(80, 99),
            'temp_range': f"{random.randint(-10, 0)}°C to {random.randint(40, 60)}°C",
            'humidity_range': '10% - 90%',
            'voltage': random.choice(['110V', '220V', '240V']),
            'daily_maint': 'Visual inspection',
            'weekly_maint': 'Clean filters',
            'monthly_maint': 'Full system check',
            'heading': random.choice(['Welcome', 'About Us', 'Products', 'Services']),
            'section_title': random.choice(['Features', 'Overview', 'Details', 'Benefits']),
            'content': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
            'paragraph_1': 'This is the first paragraph with important information.',
            'paragraph_2': 'This is the second paragraph with additional details.',
            'link_1': '/products',
            'link_2': '/services',
            'link_1_text': 'View Products',
            'link_2_text': 'Our Services',
            'mood': random.choice(['productive', 'reflective', 'challenging', 'interesting']),
            'activity_1': random.choice(['working on projects', 'reading', 'exercising']),
            'activity_2': random.choice(['planning', 'meeting friends', 'learning new skills']),
            'topic': random.choice(['career goals', 'personal growth', 'health', 'relationships']),
            'reflection': 'Important insights gained today.',
            'goal_1': random.choice(['Complete project', 'Exercise', 'Study']),
            'goal_2': random.choice(['Call family', 'Organize workspace', 'Plan week']),
            'goal_3': random.choice(['Read chapter', 'Practice skill', 'Review notes']),
            'point_1': 'Key observation from today',
            'point_2': 'Important reminder',
            'point_3': 'Follow-up needed',
            'action_1': 'Complete task A',
            'action_2': 'Schedule meeting',
            'reminder_1': 'Check calendar',
            'reminder_2': 'Send email',
            'item': random.choice(['Consulting Services', 'Software License', 'Professional Services']),
        }

        # Fill template
        try:
            return template.format(**replacements)
        except KeyError as e:
            # If keys are still missing, fill with placeholder
            for key in ['date', 'company', 'jurisdiction', 'title']:
                template = template.replace('{' + key + '}', f'[{key}]')
            return template

    def generate_file(self, category: str, index: int) -> Dict:
        """Generate a single synthetic file."""
        # Get template for category
        templates = self.templates.get(category)
        if not templates:
            # Use generic template
            templates = [f"# {category.replace('_', ' ').title()}\n\nSample content for {category} document.\nGenerated for training purposes."]

        template = random.choice(templates)
        content = self._fill_template(template, category)

        # Get extension
        extensions = self.extensions.get(category, ['.txt'])
        ext = random.choice(extensions)

        # Generate filename
        filename = f"{category}_{index:04d}{ext}"

        # Create category directory
        category_dir = self.output_dir / category
        category_dir.mkdir(exist_ok=True)

        # Write file
        file_path = category_dir / filename

        try:
            if ext in ['.txt', '.md', '.py', '.js', '.h', '.hpp', '.json', '.yaml', '.ini',
                       '.conf', '.html', '.css', '.csv', '.log', '.sh', '.ps1', '.rst']:
                # Text files
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            else:
                # Binary files - create placeholder
                with open(file_path, 'wb') as f:
                    f.write(b'SYNTHETIC_DATA_PLACEHOLDER')
        except Exception as e:
            print(f"Warning: Could not write {file_path}: {e}")
            return None

        return {
            'file_path': str(file_path.absolute()),
            'document_type': category,
            'confidence': 1.0,
            'method': 'synthetic'
        }

    def generate_dataset(self, samples_per_category: int = 100, balance_threshold: int = 500):
        """
        Generate synthetic training dataset.

        Args:
            samples_per_category: Base number of samples per category
            balance_threshold: Generate more samples for underrepresented classes
        """
        print(f"Generating synthetic training data...")
        print(f"  Output directory: {self.output_dir}")
        print(f"  Categories: {len(self.categories)}")
        print(f"  Samples per category: {samples_per_category}")

        records = []
        total_files = 0

        for category in self.categories:
            print(f"\nGenerating {category}...")

            # Generate samples
            for i in range(samples_per_category):
                result = self.generate_file(category, i)
                if result:
                    records.append(result)
                    total_files += 1

                if (i + 1) % 50 == 0:
                    print(f"  Generated {i + 1}/{samples_per_category}")

        # Write to CSV
        print(f"\nWriting CSV to {self.csv_output}...")
        with open(self.csv_output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['file_path', 'document_type', 'confidence', 'method'])
            writer.writeheader()
            writer.writerows(records)

        print(f"\nGeneration complete!")
        print(f"  Total files: {total_files}")
        print(f"  Categories: {len(self.categories)}")
        print(f"  CSV: {self.csv_output}")


def main():
    """Generate synthetic training data."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic training data for CogniSys classifier")
    parser.add_argument('--samples', type=int, default=100, help='Samples per category')
    parser.add_argument('--output-dir', default='synthetic_data', help='Output directory')
    parser.add_argument('--csv', default='synthetic_training_data.csv', help='CSV output file')

    args = parser.parse_args()

    generator = SyntheticDataGenerator(output_dir=args.output_dir, csv_output=args.csv)
    generator.generate_dataset(samples_per_category=args.samples)


if __name__ == '__main__':
    main()
