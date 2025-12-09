#!/usr/bin/env python3
"""
CogniSys Custom MCP Server
Exposes CogniSys classification and organization operations via MCP protocol
"""

import asyncio
import sqlite3
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import mcp.server.stdio
import mcp.types as types


# Initialize MCP Server
app = Server("cognisys")

# Database path
DB_PATH = Path(__file__).parent.parent.parent / 'cognisys' / 'data' / 'training' / 'cognisys_ml.db'
ORGANIZED_ROOT = Path("C:/Users/kjfle/Documents/Organized_V2")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available CogniSys tools"""
    return [
        Tool(
            name="classify_file",
            description="Classify a file using CogniSys ML pipeline. Returns document type and confidence score.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the file to classify"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="get_statistics",
            description="Get CogniSys classification statistics including document counts, confidence scores, and domain distribution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "detailed": {
                        "type": "boolean",
                        "description": "Include detailed breakdown by type",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="query_documents",
            description="Query CogniSys database with filters. Search by document type, confidence, date range, or filename pattern.",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_type": {
                        "type": "string",
                        "description": "Filter by document type (e.g., 'financial_invoice', 'automotive_technical')"
                    },
                    "min_confidence": {
                        "type": "number",
                        "description": "Minimum confidence score (0.0 to 1.0)"
                    },
                    "max_confidence": {
                        "type": "number",
                        "description": "Maximum confidence score (0.0 to 1.0)"
                    },
                    "filename_pattern": {
                        "type": "string",
                        "description": "SQL LIKE pattern for filename (e.g., '%BMW%', '%.pdf')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="reclassify_file",
            description="Manually reclassify a file to a new document type. Updates database and moves file to correct location.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "integer",
                        "description": "Database ID of the file"
                    },
                    "new_type": {
                        "type": "string",
                        "description": "New document type to assign"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score for new classification (0.0 to 1.0)",
                        "default": 1.0
                    }
                },
                "required": ["file_id", "new_type"]
            }
        ),
        Tool(
            name="get_review_candidates",
            description="Get files that need manual review (low confidence, unknown type, or flagged for review).",
            inputSchema={
                "type": "object",
                "properties": {
                    "priority": {
                        "type": "string",
                        "enum": ["critical", "high", "all"],
                        "description": "Priority level for review candidates",
                        "default": "critical"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of candidates to return",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="get_document_details",
            description="Get detailed information about a specific document including full metadata, classification history, and file location.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "integer",
                        "description": "Database ID of the file"
                    }
                },
                "required": ["file_id"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""

    if name == "get_statistics":
        return await get_statistics(arguments.get("detailed", False))

    elif name == "query_documents":
        return await query_documents(
            document_type=arguments.get("document_type"),
            min_confidence=arguments.get("min_confidence"),
            max_confidence=arguments.get("max_confidence"),
            filename_pattern=arguments.get("filename_pattern"),
            limit=arguments.get("limit", 50)
        )

    elif name == "classify_file":
        return await classify_file(arguments["file_path"])

    elif name == "reclassify_file":
        return await reclassify_file(
            file_id=arguments["file_id"],
            new_type=arguments["new_type"],
            confidence=arguments.get("confidence", 1.0)
        )

    elif name == "get_review_candidates":
        return await get_review_candidates(
            priority=arguments.get("priority", "critical"),
            limit=arguments.get("limit", 20)
        )

    elif name == "get_document_details":
        return await get_document_details(arguments["file_id"])

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def get_statistics(detailed: bool = False) -> list[TextContent]:
    """Get CogniSys classification statistics"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # Total documents
        cursor.execute("SELECT COUNT(*) FROM documents")
        total_count = cursor.fetchone()[0]

        # Average confidence
        cursor.execute("SELECT AVG(confidence) FROM documents WHERE confidence IS NOT NULL")
        avg_confidence = cursor.fetchone()[0] or 0

        # Documents by type
        cursor.execute("""
            SELECT document_type, COUNT(*) as count
            FROM documents
            GROUP BY document_type
            ORDER BY count DESC
        """)
        types_distribution = cursor.fetchall()

        # Confidence distribution
        cursor.execute("""
            SELECT
                CASE
                    WHEN confidence >= 0.90 THEN 'Very High (>=90%)'
                    WHEN confidence >= 0.75 THEN 'High (75-90%)'
                    WHEN confidence >= 0.50 THEN 'Medium (50-75%)'
                    WHEN confidence >= 0.25 THEN 'Low (25-50%)'
                    ELSE 'Very Low (<25%)'
                END as conf_level,
                COUNT(*) as count
            FROM documents
            WHERE confidence IS NOT NULL
            GROUP BY conf_level
        """)
        confidence_distribution = cursor.fetchall()

        conn.close()

        # Format response
        response = f"""CogniSys Classification Statistics
{'=' * 50}

Total Documents: {total_count:,}
Average Confidence: {avg_confidence:.2%}

Confidence Distribution:
"""
        for level, count in confidence_distribution:
            percentage = (count / total_count * 100) if total_count > 0 else 0
            response += f"  {level:<25} {count:>6} ({percentage:>5.1f}%)\n"

        if detailed:
            response += f"\nDocument Types (Top 15):\n"
            for doc_type, count in types_distribution[:15]:
                percentage = (count / total_count * 100) if total_count > 0 else 0
                response += f"  {doc_type:<30} {count:>6} ({percentage:>5.1f}%)\n"
        else:
            response += f"\nTop 5 Document Types:\n"
            for doc_type, count in types_distribution[:5]:
                percentage = (count / total_count * 100) if total_count > 0 else 0
                response += f"  {doc_type:<30} {count:>6} ({percentage:>5.1f}%)\n"

        return [TextContent(type="text", text=response)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error getting statistics: {str(e)}")]


async def query_documents(
    document_type: Optional[str] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    filename_pattern: Optional[str] = None,
    limit: int = 50
) -> list[TextContent]:
    """Query documents with filters"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # Build query
        query = "SELECT id, file_name, document_type, confidence, file_path FROM documents WHERE 1=1"
        params = []

        if document_type:
            query += " AND document_type = ?"
            params.append(document_type)

        if min_confidence is not None:
            query += " AND confidence >= ?"
            params.append(min_confidence)

        if max_confidence is not None:
            query += " AND confidence <= ?"
            params.append(max_confidence)

        if filename_pattern:
            query += " AND file_name LIKE ?"
            params.append(filename_pattern)

        query += f" ORDER BY confidence ASC LIMIT {limit}"

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        if not results:
            return [TextContent(type="text", text="No documents found matching the criteria.")]

        # Format response
        response = f"Found {len(results)} document(s):\n\n"
        for doc_id, filename, doc_type, confidence, filepath in results:
            conf_str = f"{confidence:.2%}" if confidence else "N/A"
            response += f"[{doc_id}] {filename}\n"
            response += f"  Type: {doc_type}\n"
            response += f"  Confidence: {conf_str}\n"
            response += f"  Path: {filepath}\n\n"

        return [TextContent(type="text", text=response)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error querying documents: {str(e)}")]


async def classify_file(file_path: str) -> list[TextContent]:
    """Classify a file using CogniSys"""
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return [TextContent(type="text", text=f"File not found: {file_path}")]

        # For now, return a placeholder
        # In production, this would call the actual ML classification pipeline
        response = f"""File Classification Request
{'=' * 50}

File: {file_path}
Status: Classification pipeline integration pending

Note: This tool will be connected to the CogniSys ML pipeline
to provide real-time file classification. Currently in development.

To classify files now, use:
  python scripts/workflows/auto_organize.py --file "{file_path}"
"""

        return [TextContent(type="text", text=response)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error classifying file: {str(e)}")]


async def reclassify_file(file_id: int, new_type: str, confidence: float = 1.0) -> list[TextContent]:
    """Reclassify a file"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # Get current file info
        cursor.execute("SELECT file_name, document_type, file_path FROM documents WHERE id = ?", (file_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return [TextContent(type="text", text=f"File ID {file_id} not found in database.")]

        filename, old_type, old_path = result

        # Update database
        cursor.execute("""
            UPDATE documents
            SET document_type = ?, confidence = ?
            WHERE id = ?
        """, (new_type, confidence, file_id))

        conn.commit()
        conn.close()

        response = f"""File Reclassified Successfully
{'=' * 50}

File ID: {file_id}
Filename: {filename}
Old Type: {old_type}
New Type: {new_type}
Confidence: {confidence:.2%}

Note: File will be moved to new location on next reorganization run.
Run: python scripts/workflows/reorganize_function_form.py --execute
"""

        return [TextContent(type="text", text=response)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error reclassifying file: {str(e)}")]


async def get_review_candidates(priority: str = "critical", limit: int = 20) -> list[TextContent]:
    """Get files needing manual review"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        if priority == "critical":
            query = """
                SELECT id, file_name, document_type, confidence
                FROM documents
                WHERE confidence < 0.50 OR document_type = 'unknown'
                ORDER BY confidence ASC
                LIMIT ?
            """
        elif priority == "high":
            query = """
                SELECT id, file_name, document_type, confidence
                FROM documents
                WHERE confidence < 0.75 OR document_type IN ('unknown', 'general_document')
                ORDER BY confidence ASC
                LIMIT ?
            """
        else:  # all
            query = """
                SELECT id, file_name, document_type, confidence
                FROM documents
                WHERE confidence < 0.75 OR document_type IN ('unknown', 'general_document', 'form')
                ORDER BY confidence ASC
                LIMIT ?
            """

        cursor.execute(query, (limit,))
        results = cursor.fetchall()
        conn.close()

        if not results:
            return [TextContent(type="text", text=f"No files need review at {priority} priority level.")]

        response = f"Review Candidates ({priority.upper()} priority) - {len(results)} file(s):\n\n"
        for doc_id, filename, doc_type, confidence in results:
            conf_str = f"{confidence:.2%}" if confidence else "0%"
            response += f"[{doc_id}] {filename}\n"
            response += f"  Current Type: {doc_type}\n"
            response += f"  Confidence: {conf_str}\n"
            response += f"  Action: Review and reclassify if needed\n\n"

        return [TextContent(type="text", text=response)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error getting review candidates: {str(e)}")]


async def get_document_details(file_id: int) -> list[TextContent]:
    """Get detailed document information"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, file_name, file_path, document_type, confidence, created_date
            FROM documents
            WHERE id = ?
        """, (file_id,))

        result = cursor.fetchone()
        conn.close()

        if not result:
            return [TextContent(type="text", text=f"Document ID {file_id} not found.")]

        doc_id, filename, filepath, doc_type, confidence, created_date = result

        # Check if file exists
        file_exists = os.path.exists(filepath) if filepath else False

        response = f"""Document Details
{'=' * 50}

ID: {doc_id}
Filename: {filename}
Document Type: {doc_type}
Confidence: {confidence:.2%} if confidence else "N/A"
Created: {created_date or "Unknown"}

File Location:
  Path: {filepath or "Unknown"}
  Exists: {"Yes" if file_exists else "No"}

Actions:
  - Reclassify: reclassify_file(file_id={doc_id}, new_type="...")
  - Query similar: query_documents(document_type="{doc_type}")
"""

        return [TextContent(type="text", text=response)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error getting document details: {str(e)}")]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
