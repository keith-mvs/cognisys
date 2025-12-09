"""
CogniSys Web Dashboard
Flask-based review and management interface
"""

from flask import Flask, render_template, jsonify, request, send_file
import sqlite3
from pathlib import Path
import json
from datetime import datetime

app = Flask(__name__)
app.config['DATABASE'] = '.cognisys/file_registry.db'


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    """Main dashboard"""
    return render_template('dashboard.html')


@app.route('/api/stats')
def get_stats():
    """Get database statistics"""
    conn = get_db()
    cursor = conn.cursor()

    # Total files
    cursor.execute("SELECT COUNT(*) as total FROM file_registry")
    total = cursor.fetchone()['total']

    # By state
    cursor.execute("""
        SELECT canonical_state, COUNT(*) as count
        FROM file_registry
        GROUP BY canonical_state
    """)
    by_state = {row['canonical_state']: row['count'] for row in cursor.fetchall()}

    # By document type (top 15)
    cursor.execute("""
        SELECT document_type, COUNT(*) as count
        FROM file_registry
        WHERE document_type IS NOT NULL
        GROUP BY document_type
        ORDER BY count DESC
        LIMIT 15
    """)
    by_type = [dict(row) for row in cursor.fetchall()]

    # By classification method
    cursor.execute("""
        SELECT classification_method, COUNT(*) as count
        FROM file_registry
        WHERE classification_method IS NOT NULL
        GROUP BY classification_method
    """)
    by_method = {row['classification_method']: row['count'] for row in cursor.fetchall()}

    # Duplicates
    cursor.execute("SELECT COUNT(*) as count FROM file_registry WHERE is_duplicate = 1")
    duplicates = cursor.fetchone()['count']

    # Low confidence
    cursor.execute("""
        SELECT COUNT(*) as count FROM file_registry
        WHERE confidence < 0.70 AND confidence > 0
    """)
    low_confidence = cursor.fetchone()['count']

    conn.close()

    return jsonify({
        'total': total,
        'by_state': by_state,
        'by_type': by_type,
        'by_method': by_method,
        'duplicates': duplicates,
        'low_confidence': low_confidence
    })


@app.route('/api/files')
def get_files():
    """Get paginated file list"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    filter_type = request.args.get('type', None)
    filter_state = request.args.get('state', None)

    conn = get_db()
    cursor = conn.cursor()

    # Build query
    query = "SELECT * FROM file_registry WHERE 1=1"
    params = []

    if filter_type:
        query += " AND document_type = ?"
        params.append(filter_type)

    if filter_state:
        query += " AND canonical_state = ?"
        params.append(filter_state)

    query += " ORDER BY file_id DESC LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])

    cursor.execute(query, params)
    files = [dict(row) for row in cursor.fetchall()]

    # Get total count
    count_query = "SELECT COUNT(*) as total FROM file_registry WHERE 1=1"
    count_params = []
    if filter_type:
        count_query += " AND document_type = ?"
        count_params.append(filter_type)
    if filter_state:
        count_query += " AND canonical_state = ?"
        count_params.append(filter_state)

    cursor.execute(count_query, count_params)
    total = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        'files': files,
        'total': total,
        'page': page,
        'per_page': per_page
    })


@app.route('/api/file/<int:file_id>')
def get_file(file_id):
    """Get single file details"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM file_registry WHERE file_id = ?", (file_id,))
    file = cursor.fetchone()

    if not file:
        return jsonify({'error': 'File not found'}), 404

    conn.close()
    return jsonify(dict(file))


@app.route('/api/file/<int:file_id>/update', methods=['POST'])
def update_file(file_id):
    """Update file classification"""
    data = request.json
    doc_type = data.get('document_type')
    confidence = data.get('confidence', 1.0)

    if not doc_type:
        return jsonify({'error': 'document_type required'}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE file_registry
        SET document_type = ?,
            confidence = ?,
            classification_method = 'manual_correction',
            updated_at = datetime('now')
        WHERE file_id = ?
    """, (doc_type, confidence, file_id))

    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/search')
def search_files():
    """Search files by name"""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 50, type=int)

    if len(query) < 3:
        return jsonify({'files': []})

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM file_registry
        WHERE original_path LIKE ?
        ORDER BY file_id DESC
        LIMIT ?
    """, (f'%{query}%', limit))

    files = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'files': files})


@app.route('/api/low_confidence')
def get_low_confidence():
    """Get low confidence classifications for review"""
    limit = request.args.get('limit', 100, type=int)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM file_registry
        WHERE confidence < 0.70 AND confidence > 0
        ORDER BY confidence ASC
        LIMIT ?
    """, (limit,))

    files = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'files': files})


@app.route('/api/export')
def export_data():
    """Export data as JSON"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM file_registry")
    files = [dict(row) for row in cursor.fetchall()]

    conn.close()

    # Create JSON file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'cognisys_export_{timestamp}.json'

    with open(filename, 'w') as f:
        json.dump(files, f, indent=2)

    return send_file(filename, as_attachment=True)


def main():
    """Run development server"""
    print("=" * 80)
    print("COGNISYS WEB DASHBOARD")
    print("=" * 80)
    print()
    print("Starting server at http://localhost:5000")
    print()
    print("Features:")
    print("  - View classification statistics")
    print("  - Browse and search files")
    print("  - Review low-confidence classifications")
    print("  - Manual corrections")
    print("  - Export data")
    print()
    print("Press CTRL+C to stop")
    print("=" * 80)
    print()

    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
