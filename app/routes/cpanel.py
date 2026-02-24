"""
Server Control Panel Routes
A lightweight cPanel-like management interface for VPS administration.
Features: System Monitor, File Manager, Log Viewer, Database Browser, Service Control.
"""

import os
import json
import logging
import subprocess
import sqlite3
import platform
import datetime
from pathlib import Path
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app, jsonify, send_file, abort
)
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)
cpanel_bp = Blueprint('cpanel', __name__)

# Base directory for file manager (restrict to project root)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def admin_required(f):
    """Decorator: require admin role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


def _safe_path(requested_path):
    """Ensure the requested path is within BASE_DIR (prevent directory traversal)."""
    abs_path = os.path.abspath(os.path.join(BASE_DIR, requested_path))
    if not abs_path.startswith(os.path.abspath(BASE_DIR)):
        return None
    return abs_path


# ── System Monitor ──────────────────────────────────────────────
def _get_system_info():
    """Get system information."""
    info = {
        'hostname': platform.node(),
        'os': f'{platform.system()} {platform.release()}',
        'python': platform.python_version(),
        'architecture': platform.machine(),
        'processor': platform.processor() or 'N/A',
    }

    # Uptime
    try:
        if platform.system() == 'Linux':
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                mins = int((uptime_seconds % 3600) // 60)
                info['uptime'] = f'{days}d {hours}h {mins}m'
        else:
            info['uptime'] = 'N/A'
    except Exception:
        info['uptime'] = 'N/A'

    return info


def _get_cpu_info():
    """Get CPU usage."""
    try:
        if platform.system() == 'Linux':
            load1, load5, load15 = os.getloadavg()
            cpu_count = os.cpu_count() or 1
            usage_pct = min(100, (load1 / cpu_count) * 100)
            return {
                'usage': round(usage_pct, 1),
                'load_1m': round(load1, 2),
                'load_5m': round(load5, 2),
                'load_15m': round(load15, 2),
                'cores': cpu_count
            }
        else:
            return {'usage': 0, 'load_1m': 0, 'load_5m': 0, 'load_15m': 0, 'cores': os.cpu_count() or 1}
    except Exception:
        return {'usage': 0, 'load_1m': 0, 'load_5m': 0, 'load_15m': 0, 'cores': 1}


def _get_memory_info():
    """Get memory usage."""
    try:
        if platform.system() == 'Linux':
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = int(parts[1].strip().split()[0])  # kB
                        meminfo[key] = val

            total = meminfo.get('MemTotal', 0) / 1024  # MB
            available = meminfo.get('MemAvailable', meminfo.get('MemFree', 0)) / 1024
            used = total - available
            pct = (used / total * 100) if total > 0 else 0
            return {
                'total_mb': round(total),
                'used_mb': round(used),
                'available_mb': round(available),
                'percent': round(pct, 1)
            }
        else:
            return {'total_mb': 0, 'used_mb': 0, 'available_mb': 0, 'percent': 0}
    except Exception:
        return {'total_mb': 0, 'used_mb': 0, 'available_mb': 0, 'percent': 0}


def _get_disk_info():
    """Get disk usage."""
    try:
        stat = os.statvfs(BASE_DIR) if platform.system() != 'Windows' else None
        if stat:
            total = (stat.f_blocks * stat.f_frsize) / (1024 ** 3)  # GB
            free = (stat.f_bfree * stat.f_frsize) / (1024 ** 3)
            used = total - free
            pct = (used / total * 100) if total > 0 else 0
            return {
                'total_gb': round(total, 1),
                'used_gb': round(used, 1),
                'free_gb': round(free, 1),
                'percent': round(pct, 1)
            }
        else:
            # Windows fallback
            import shutil
            usage = shutil.disk_usage(BASE_DIR)
            return {
                'total_gb': round(usage.total / (1024**3), 1),
                'used_gb': round(usage.used / (1024**3), 1),
                'free_gb': round(usage.free / (1024**3), 1),
                'percent': round(usage.used / usage.total * 100, 1)
            }
    except Exception:
        return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}


# ── Routes ──────────────────────────────────────────────────────

@cpanel_bp.route('/cpanel')
@admin_required
def dashboard():
    """Main cPanel dashboard with system overview."""
    system = _get_system_info()
    cpu = _get_cpu_info()
    memory = _get_memory_info()
    disk = _get_disk_info()

    # Get recent processes (top 15)
    processes = []
    try:
        if platform.system() == 'Linux':
            result = subprocess.run(
                ['ps', 'aux', '--sort=-pcpu'],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split('\n')
            for line in lines[1:16]:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append({
                        'user': parts[0],
                        'pid': parts[1],
                        'cpu': parts[2],
                        'mem': parts[3],
                        'command': parts[10][:80]
                    })
    except Exception as e:
        logger.warning(f'Process list error: {e}')

    return render_template('admin/cpanel/dashboard.html',
                           system=system, cpu=cpu, memory=memory,
                           disk=disk, processes=processes)


@cpanel_bp.route('/cpanel/files')
@cpanel_bp.route('/cpanel/files/<path:subpath>')
@admin_required
def file_manager(subpath=''):
    """Browse files and directories."""
    abs_path = _safe_path(subpath)
    if abs_path is None:
        flash('Invalid path.', 'danger')
        return redirect(url_for('cpanel.file_manager'))

    if not os.path.exists(abs_path):
        flash('Path not found.', 'danger')
        return redirect(url_for('cpanel.file_manager'))

    # If it's a file, show file viewer
    if os.path.isfile(abs_path):
        file_content = None
        is_text = False
        file_size = os.path.getsize(abs_path)
        ext = os.path.splitext(abs_path)[1].lower()

        text_extensions = {'.py', '.html', '.css', '.js', '.json', '.txt', '.md',
                          '.yml', '.yaml', '.cfg', '.ini', '.env', '.sh', '.conf',
                          '.log', '.csv', '.xml', '.sql', '.toml', '.example'}

        if ext in text_extensions and file_size < 500_000:
            try:
                with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                    file_content = f.read()
                is_text = True
            except Exception:
                pass

        return render_template('admin/cpanel/file_view.html',
                             file_path=subpath, file_content=file_content,
                             is_text=is_text, file_size=file_size, ext=ext)

    # Directory listing
    items = []
    try:
        for entry in sorted(os.scandir(abs_path), key=lambda e: (not e.is_dir(), e.name.lower())):
            item = {
                'name': entry.name,
                'is_dir': entry.is_dir(),
                'path': os.path.relpath(entry.path, BASE_DIR).replace('\\', '/'),
            }
            try:
                stat = entry.stat()
                item['size'] = stat.st_size
                item['modified'] = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
            except Exception:
                item['size'] = 0
                item['modified'] = 'N/A'

            # Skip hidden files and __pycache__, .git, etc.
            if entry.name.startswith('.') and entry.name not in ['.env', '.env.example']:
                continue
            if entry.name in ['__pycache__', 'node_modules', '.git']:
                continue

            items.append(item)
    except PermissionError:
        flash('Permission denied.', 'danger')

    # Build breadcrumbs
    breadcrumbs = [{'name': 'Root', 'path': ''}]
    if subpath:
        parts = subpath.split('/')
        for i, part in enumerate(parts):
            breadcrumbs.append({
                'name': part,
                'path': '/'.join(parts[:i + 1])
            })

    return render_template('admin/cpanel/file_manager.html',
                         items=items, current_path=subpath,
                         breadcrumbs=breadcrumbs)


@cpanel_bp.route('/cpanel/files/download/<path:subpath>')
@admin_required
def download_file(subpath):
    """Download a file."""
    abs_path = _safe_path(subpath)
    if abs_path is None or not os.path.isfile(abs_path):
        flash('File not found.', 'danger')
        return redirect(url_for('cpanel.file_manager'))
    return send_file(abs_path, as_attachment=True)


@cpanel_bp.route('/cpanel/files/edit/<path:subpath>', methods=['POST'])
@admin_required
def edit_file(subpath):
    """Save edited file content."""
    abs_path = _safe_path(subpath)
    if abs_path is None or not os.path.isfile(abs_path):
        flash('File not found.', 'danger')
        return redirect(url_for('cpanel.file_manager'))

    content = request.form.get('content', '')
    try:
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        flash(f'File saved: {os.path.basename(abs_path)}', 'success')
    except Exception as e:
        flash(f'Error saving file: {e}', 'danger')

    return redirect(url_for('cpanel.file_manager', subpath=subpath))


@cpanel_bp.route('/cpanel/files/delete/<path:subpath>', methods=['POST'])
@admin_required
def delete_file(subpath):
    """Delete a file."""
    abs_path = _safe_path(subpath)
    if abs_path is None:
        flash('Invalid path.', 'danger')
        return redirect(url_for('cpanel.file_manager'))

    parent = os.path.relpath(os.path.dirname(abs_path), BASE_DIR).replace('\\', '/')
    if parent == '.':
        parent = ''

    try:
        if os.path.isfile(abs_path):
            os.remove(abs_path)
            flash(f'Deleted: {os.path.basename(abs_path)}', 'success')
        elif os.path.isdir(abs_path):
            import shutil
            shutil.rmtree(abs_path)
            flash(f'Deleted directory: {os.path.basename(abs_path)}', 'success')
    except Exception as e:
        flash(f'Error deleting: {e}', 'danger')

    return redirect(url_for('cpanel.file_manager', subpath=parent))


@cpanel_bp.route('/cpanel/files/upload', methods=['POST'])
@admin_required
def upload_file():
    """Upload a file to the current directory."""
    target_path = request.form.get('target_path', '')
    abs_dir = _safe_path(target_path)

    if abs_dir is None or not os.path.isdir(abs_dir):
        flash('Invalid upload directory.', 'danger')
        return redirect(url_for('cpanel.file_manager'))

    uploaded = request.files.get('file')
    if uploaded and uploaded.filename:
        filename = uploaded.filename
        dest = os.path.join(abs_dir, filename)
        uploaded.save(dest)
        flash(f'Uploaded: {filename}', 'success')
    else:
        flash('No file selected.', 'warning')

    return redirect(url_for('cpanel.file_manager', subpath=target_path))


# ── Log Viewer ──────────────────────────────────────────────────

@cpanel_bp.route('/cpanel/logs')
@admin_required
def log_viewer():
    """View application logs."""
    log_dir = os.path.join(BASE_DIR, 'logs')
    log_files = []

    if os.path.isdir(log_dir):
        for f in sorted(os.listdir(log_dir)):
            fp = os.path.join(log_dir, f)
            if os.path.isfile(fp):
                log_files.append({
                    'name': f,
                    'size': os.path.getsize(fp),
                    'modified': datetime.datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M')
                })

    # View selected log
    selected_log = request.args.get('file', 'spkr.log')
    lines_count = int(request.args.get('lines', 100))
    log_content = ''

    log_path = os.path.join(log_dir, selected_log)
    if os.path.isfile(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
                log_content = ''.join(all_lines[-lines_count:])
        except Exception as e:
            log_content = f'Error reading log: {e}'

    return render_template('admin/cpanel/logs.html',
                         log_files=log_files, log_content=log_content,
                         selected_log=selected_log, lines_count=lines_count)


# ── Database Browser ────────────────────────────────────────────

@cpanel_bp.route('/cpanel/database')
@admin_required
def database_browser():
    """Browse SQLite database tables."""
    db_path = None
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')

    if 'sqlite' in db_uri:
        db_path = db_uri.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = os.path.join(BASE_DIR, 'instance', db_path)
            if not os.path.exists(db_path):
                db_path = os.path.join(BASE_DIR, db_path)

    tables = []
    table_data = None
    selected_table = request.args.get('table', '')
    page = int(request.args.get('page', 1))
    per_page = 25

    if db_path and os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get table list
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]

            # Get table data
            if selected_table and selected_table in tables:
                # Count rows
                cursor.execute(f'SELECT COUNT(*) FROM "{selected_table}"')
                total_rows = cursor.fetchone()[0]

                # Get columns
                cursor.execute(f'PRAGMA table_info("{selected_table}")')
                columns = [{'name': row[1], 'type': row[2]} for row in cursor.fetchall()]

                # Get data with pagination
                offset = (page - 1) * per_page
                cursor.execute(f'SELECT * FROM "{selected_table}" LIMIT {per_page} OFFSET {offset}')
                rows = [dict(row) for row in cursor.fetchall()]

                total_pages = max(1, (total_rows + per_page - 1) // per_page)

                table_data = {
                    'name': selected_table,
                    'columns': columns,
                    'rows': rows,
                    'total_rows': total_rows,
                    'page': page,
                    'total_pages': total_pages,
                    'per_page': per_page
                }

            conn.close()
        except Exception as e:
            flash(f'Database error: {e}', 'danger')
            logger.error(f'Database browser error: {e}')
    else:
        flash('Database file not found.', 'warning')

    return render_template('admin/cpanel/database.html',
                         tables=tables, table_data=table_data,
                         selected_table=selected_table)


@cpanel_bp.route('/cpanel/database/query', methods=['POST'])
@admin_required
def database_query():
    """Execute a raw SQL query (SELECT only for safety)."""
    query = request.form.get('query', '').strip()

    if not query:
        return jsonify({'error': 'Empty query'}), 400

    # Safety: only allow SELECT queries
    if not query.upper().startswith('SELECT'):
        return jsonify({'error': 'Only SELECT queries are allowed for safety.'}), 400

    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_path = db_uri.replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        db_path = os.path.join(BASE_DIR, 'instance', db_path)
        if not os.path.exists(db_path):
            db_path = os.path.join(BASE_DIR, db_path)

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query)
        rows = [dict(row) for row in cursor.fetchall()[:200]]
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        conn.close()
        return jsonify({'columns': columns, 'rows': rows, 'count': len(rows)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ── Service Control ─────────────────────────────────────────────

@cpanel_bp.route('/cpanel/services')
@admin_required
def services():
    """View and manage system services."""
    service_list = []

    if platform.system() == 'Linux':
        services_to_check = ['instagrampost', 'nginx', 'postgresql', 'redis-server', 'gunicorn']
        for svc in services_to_check:
            status = 'unknown'
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', svc],
                    capture_output=True, text=True, timeout=5
                )
                status = result.stdout.strip()
            except Exception:
                status = 'not-found'

            service_list.append({'name': svc, 'status': status})

    return render_template('admin/cpanel/services.html', services=service_list)


@cpanel_bp.route('/cpanel/services/restart/<service_name>', methods=['POST'])
@admin_required
def restart_service(service_name):
    """Restart a system service."""
    allowed = ['instagrampost', 'nginx']
    if service_name not in allowed:
        flash(f'Service {service_name} is not in allowed list.', 'danger')
        return redirect(url_for('cpanel.services'))

    try:
        result = subprocess.run(
            ['systemctl', 'restart', service_name],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            flash(f'Service {service_name} restarted successfully.', 'success')
        else:
            flash(f'Failed to restart {service_name}: {result.stderr}', 'danger')
    except Exception as e:
        flash(f'Error: {e}', 'danger')

    return redirect(url_for('cpanel.services'))


# ── Quick Terminal ──────────────────────────────────────────────

@cpanel_bp.route('/cpanel/terminal', methods=['GET', 'POST'])
@admin_required
def terminal():
    """Simple command execution (limited safe commands)."""
    output = ''
    command = ''

    if request.method == 'POST':
        command = request.form.get('command', '').strip()

        # Whitelist of safe command prefixes
        safe_prefixes = [
            'ls', 'cat', 'head', 'tail', 'grep', 'find', 'wc', 'df', 'du',
            'free', 'uptime', 'whoami', 'pwd', 'date', 'pip list', 'pip show',
            'python --version', 'python3 --version', 'nginx -t',
            'systemctl status', 'journalctl', 'netstat', 'ss',
            'git status', 'git log', 'git branch', 'git diff',
            'env', 'printenv', 'uname',
        ]

        is_safe = any(command.startswith(prefix) for prefix in safe_prefixes)

        if not is_safe:
            output = f'⚠️ Command not allowed. Safe commands: {", ".join(safe_prefixes)}'
        else:
            try:
                result = subprocess.run(
                    command, shell=True,
                    capture_output=True, text=True,
                    timeout=15, cwd=BASE_DIR
                )
                output = result.stdout
                if result.stderr:
                    output += '\n--- STDERR ---\n' + result.stderr
                if not output.strip():
                    output = '(no output)'
            except subprocess.TimeoutExpired:
                output = '⚠️ Command timed out (15s limit).'
            except Exception as e:
                output = f'Error: {e}'

    return render_template('admin/cpanel/terminal.html',
                         output=output, command=command)
