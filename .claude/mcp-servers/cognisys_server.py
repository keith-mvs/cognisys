#!/usr/bin/env python3
"""
CogniSys MCP Server
Provides Claude Code with direct access to CogniSys ML database and classification system
"""

import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Any
import requests

# Add CogniSys to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "cognisys" / "data" / "training" / "cognisys_ml.db"
ML_API_URL = "http://127.0.0.1:5000"


class CogniSysMCPServer:
    """MCP Server for CogniSys integration with Claude Code"""

    def __init__(self):
        self.db_path = DB_PATH

    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools for Claude Code"""
        return [
            {
                "name": "cognisys_query_documents",
                "description": "Query classified documents by type, date, or search term",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doc_type": {"type": "string", "description": "Filter by document type"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                        "search": {"type": "string", "description": "Search in filename or path"}
                    }
                }
            },
            {
                "name": "cognisys_get_classification_stats",
                "description": "Get statistics about document classifications",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "cognisys_classify_document",
                "description": "Classify a document using the CogniSys ML pipeline",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Absolute path to document"}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "cognisys_submit_feedback",
                "description": "Submit classification feedback to improve the model",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doc_id": {"type": "integer", "description": "Document ID"},
                        "correct_type": {"type": "string", "description": "Correct document type"},
                        "user_notes": {"type": "string", "description": "Additional notes"}
                    },
                    "required": ["doc_id", "correct_type"]
                }
            },
            {
                "name": "cognisys_get_categories",
                "description": "List all available document categories",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call"""
        try:
            if tool_name == "cognisys_query_documents":
                return self._query_documents(**arguments)
            elif tool_name == "cognisys_get_classification_stats":
                return self._get_classification_stats()
            elif tool_name == "cognisys_classify_document":
                return self._classify_document(**arguments)
            elif tool_name == "cognisys_submit_feedback":
                return self._submit_feedback(**arguments)
            elif tool_name == "cognisys_get_categories":
                return self._get_categories()
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": str(e)}

    def _query_documents(self, doc_type: str = None, limit: int = 10, search: str = None) -> Dict:
        """Query documents from the database"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT id, file_name, file_path, doc_type, confidence, created_at FROM documents WHERE 1=1"
        params = []

        if doc_type:
            query += " AND doc_type = ?"
            params.append(doc_type)

        if search:
            query += " AND (file_name LIKE ? OR file_path LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        documents = []
        for row in rows:
            documents.append({
                "id": row[0],
                "file_name": row[1],
                "file_path": row[2],
                "doc_type": row[3],
                "confidence": row[4],
                "created_at": row[5]
            })

        conn.close()
        return {"documents": documents, "count": len(documents)}

    def _get_classification_stats(self) -> Dict:
        """Get classification statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total documents
        cursor.execute("SELECT COUNT(*) FROM documents")
        total = cursor.fetchone()[0]

        # By type
        cursor.execute("""
            SELECT doc_type, COUNT(*) as count, AVG(confidence) as avg_conf
            FROM documents
            GROUP BY doc_type
            ORDER BY count DESC
        """)
        by_type = [{"type": row[0], "count": row[1], "avg_confidence": row[2]} for row in cursor.fetchall()]

        # Recent classifications
        cursor.execute("""
            SELECT COUNT(*) FROM documents
            WHERE datetime(created_at) > datetime('now', '-7 days')
        """)
        recent_count = cursor.fetchone()[0]

        # Feedback stats
        cursor.execute("SELECT COUNT(*) FROM feedback WHERE is_correct = 0")
        incorrect_count = cursor.fetchone()[0]

        conn.close()

        return {
            "total_documents": total,
            "by_type": by_type,
            "last_7_days": recent_count,
            "incorrect_classifications": incorrect_count
        }

    def _classify_document(self, file_path: str) -> Dict:
        """Classify a document via ML API"""
        try:
            response = requests.post(
                f"{ML_API_URL}/process/document",
                json={"file_path": file_path},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Classification failed: {str(e)}"}

    def _submit_feedback(self, doc_id: int, correct_type: str, user_notes: str = "") -> Dict:
        """Submit classification feedback"""
        try:
            response = requests.post(
                f"{ML_API_URL}/feedback/submit",
                json={
                    "doc_id": doc_id,
                    "correct_type": correct_type,
                    "user_notes": user_notes
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Feedback submission failed: {str(e)}"}

    def _get_categories(self) -> Dict:
        """Get list of all document categories"""
        try:
            response = requests.get(f"{ML_API_URL}/categories", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Failed to fetch categories: {str(e)}"}


def main():
    """MCP Server main loop"""
    server = CogniSysMCPServer()

    # Read MCP protocol messages from stdin
    for line in sys.stdin:
        try:
            message = json.loads(line)
            method = message.get("method")
            params = message.get("params", {})
            msg_id = message.get("id")

            if method == "tools/list":
                result = server.list_tools()
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = server.call_tool(tool_name, arguments)
            else:
                result = {"error": f"Unknown method: {method}"}

            # Send response
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result
            }
            print(json.dumps(response), flush=True)

        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": message.get("id") if 'message' in locals() else None,
                "error": {"code": -32603, "message": str(e)}
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
