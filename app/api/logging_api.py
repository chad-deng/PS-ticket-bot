"""
Logging API endpoints for PS Ticket Process Bot.
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
import structlog

from app.core.config import get_settings


logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/logs")
async def get_log_files():
    """
    Get list of available log files.
    
    Returns:
        List of log files with metadata.
    """
    try:
        logs_dir = Path("logs")
        
        if not logs_dir.exists():
            return JSONResponse(
                status_code=200,
                content={
                    "log_files": [],
                    "message": "No logs directory found"
                }
            )
        
        log_files = []
        for log_file in logs_dir.glob("*.log"):
            try:
                stat = log_file.stat()
                log_files.append({
                    "name": log_file.name,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified": stat.st_mtime,
                    "path": str(log_file)
                })
            except Exception as e:
                logger.warning(f"Failed to get stats for {log_file}: {e}")
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: x["modified"], reverse=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "log_files": log_files,
                "count": len(log_files)
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get log files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve log files")


@router.get("/logs/{log_file}")
async def get_log_content(
    log_file: str,
    lines: int = Query(100, description="Number of lines to return from the end"),
    search: Optional[str] = Query(None, description="Search term to filter lines")
):
    """
    Get content from a specific log file.
    
    Args:
        log_file: Name of the log file
        lines: Number of lines to return from the end
        search: Optional search term to filter lines
        
    Returns:
        Log file content.
    """
    try:
        logs_dir = Path("logs")
        log_path = logs_dir / log_file
        
        # Security check - ensure file is in logs directory
        if not str(log_path.resolve()).startswith(str(logs_dir.resolve())):
            raise HTTPException(status_code=400, detail="Invalid log file path")
        
        if not log_path.exists():
            raise HTTPException(status_code=404, detail=f"Log file {log_file} not found")
        
        # Read log file
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(log_path, 'r', encoding='latin-1') as f:
                all_lines = f.readlines()
        
        # Filter lines if search term provided
        if search:
            filtered_lines = [line for line in all_lines if search.lower() in line.lower()]
        else:
            filtered_lines = all_lines
        
        # Get last N lines
        if lines > 0:
            selected_lines = filtered_lines[-lines:]
        else:
            selected_lines = filtered_lines
        
        return JSONResponse(
            status_code=200,
            content={
                "log_file": log_file,
                "total_lines": len(all_lines),
                "filtered_lines": len(filtered_lines),
                "returned_lines": len(selected_lines),
                "search_term": search,
                "content": [line.rstrip() for line in selected_lines]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read log file {log_file}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to read log file")


@router.get("/logs/{log_file}/raw")
async def get_log_content_raw(
    log_file: str,
    lines: int = Query(100, description="Number of lines to return from the end")
):
    """
    Get raw log file content as plain text.
    
    Args:
        log_file: Name of the log file
        lines: Number of lines to return from the end
        
    Returns:
        Raw log file content as plain text.
    """
    try:
        logs_dir = Path("logs")
        log_path = logs_dir / log_file
        
        # Security check
        if not str(log_path.resolve()).startswith(str(logs_dir.resolve())):
            raise HTTPException(status_code=400, detail="Invalid log file path")
        
        if not log_path.exists():
            raise HTTPException(status_code=404, detail=f"Log file {log_file} not found")
        
        # Read log file
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
        except UnicodeDecodeError:
            with open(log_path, 'r', encoding='latin-1') as f:
                all_lines = f.readlines()
        
        # Get last N lines
        if lines > 0:
            selected_lines = all_lines[-lines:]
        else:
            selected_lines = all_lines
        
        content = ''.join(selected_lines)
        
        return PlainTextResponse(
            content=content,
            media_type="text/plain"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read raw log file {log_file}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to read log file")


@router.get("/logs/search/{search_term}")
async def search_logs(
    search_term: str,
    log_files: Optional[List[str]] = Query(None, description="Specific log files to search"),
    max_results: int = Query(100, description="Maximum number of results to return")
):
    """
    Search across log files for a specific term.
    
    Args:
        search_term: Term to search for
        log_files: Optional list of specific log files to search
        max_results: Maximum number of results to return
        
    Returns:
        Search results across log files.
    """
    try:
        logs_dir = Path("logs")
        
        if not logs_dir.exists():
            return JSONResponse(
                status_code=200,
                content={
                    "search_term": search_term,
                    "results": [],
                    "message": "No logs directory found"
                }
            )
        
        # Determine which log files to search
        if log_files:
            search_files = [logs_dir / f for f in log_files if (logs_dir / f).exists()]
        else:
            search_files = list(logs_dir.glob("*.log"))
        
        results = []
        total_matches = 0
        
        for log_file in search_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if search_term.lower() in line.lower():
                            results.append({
                                "file": log_file.name,
                                "line_number": line_num,
                                "content": line.strip(),
                                "timestamp": line.split(' - ')[0] if ' - ' in line else None
                            })
                            total_matches += 1
                            
                            if len(results) >= max_results:
                                break
                                
            except Exception as e:
                logger.warning(f"Failed to search in {log_file}: {e}")
                continue
            
            if len(results) >= max_results:
                break
        
        return JSONResponse(
            status_code=200,
            content={
                "search_term": search_term,
                "total_matches": total_matches,
                "returned_results": len(results),
                "max_results": max_results,
                "searched_files": [f.name for f in search_files],
                "results": results
            }
        )
        
    except Exception as e:
        logger.error(f"Log search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Log search failed")


@router.get("/logging/config")
async def get_logging_config():
    """
    Get current logging configuration.
    
    Returns:
        Current logging configuration and levels.
    """
    try:
        settings = get_settings()
        
        # Get current logger levels
        loggers_info = {}
        for name in ['app', 'app.services', 'app.tasks', 'app.api', 'celery', 'httpx']:
            logger_obj = logging.getLogger(name)
            loggers_info[name] = {
                "level": logging.getLevelName(logger_obj.level),
                "effective_level": logging.getLevelName(logger_obj.getEffectiveLevel()),
                "handlers_count": len(logger_obj.handlers)
            }
        
        return JSONResponse(
            status_code=200,
            content={
                "app_config": {
                    "log_level": settings.app.log_level,
                    "debug": settings.app.debug,
                    "environment": settings.app.environment
                },
                "loggers": loggers_info,
                "root_logger": {
                    "level": logging.getLevelName(logging.getLogger().level),
                    "handlers_count": len(logging.getLogger().handlers)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get logging config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve logging configuration")


@router.post("/logging/level")
async def set_log_level(
    logger_name: str = Query(..., description="Logger name to modify"),
    level: str = Query(..., description="Log level (DEBUG, INFO, WARNING, ERROR)")
):
    """
    Set log level for a specific logger.
    
    Args:
        logger_name: Name of the logger to modify
        level: New log level
        
    Returns:
        Confirmation of log level change.
    """
    try:
        # Validate log level
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if level.upper() not in valid_levels:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid log level. Must be one of: {', '.join(valid_levels)}"
            )
        
        # Set log level
        logger_obj = logging.getLogger(logger_name)
        old_level = logging.getLevelName(logger_obj.level)
        logger_obj.setLevel(getattr(logging, level.upper()))
        
        logger.info(
            "Log level changed",
            logger_name=logger_name,
            old_level=old_level,
            new_level=level.upper()
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "logger_name": logger_name,
                "old_level": old_level,
                "new_level": level.upper(),
                "message": f"Log level for {logger_name} changed from {old_level} to {level.upper()}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set log level: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set log level")


@router.get("/logging/stats")
async def get_logging_stats():
    """
    Get logging statistics.
    
    Returns:
        Statistics about log files and logging activity.
    """
    try:
        logs_dir = Path("logs")
        
        if not logs_dir.exists():
            return JSONResponse(
                status_code=200,
                content={
                    "stats": {
                        "total_log_files": 0,
                        "total_size_mb": 0,
                        "log_files": []
                    }
                }
            )
        
        log_files_stats = []
        total_size = 0
        
        for log_file in logs_dir.glob("*.log"):
            try:
                stat = log_file.stat()
                size_mb = stat.st_size / (1024 * 1024)
                total_size += size_mb
                
                # Count lines
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        line_count = sum(1 for _ in f)
                except:
                    line_count = 0
                
                log_files_stats.append({
                    "name": log_file.name,
                    "size_mb": round(size_mb, 2),
                    "line_count": line_count,
                    "modified": stat.st_mtime
                })
                
            except Exception as e:
                logger.warning(f"Failed to get stats for {log_file}: {e}")
        
        return JSONResponse(
            status_code=200,
            content={
                "stats": {
                    "total_log_files": len(log_files_stats),
                    "total_size_mb": round(total_size, 2),
                    "log_files": log_files_stats
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get logging stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve logging statistics")
