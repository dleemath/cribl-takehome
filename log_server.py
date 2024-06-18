from flask import Flask, request, jsonify, Response
from flask_openapi3 import OpenAPI, Info
import os
import gzip
import io
from flask_cors import CORS

# Define OpenAPI Info
info = Info(title='Log File API', version='1.0.0')
app = OpenAPI(__name__, info=info)
cors = CORS(app)
# Log directory and default page size
LOG_DIR = "/var/log"
DEFAULT_PAGE_SIZE = 500

@app.post('/logs')
def get_log_file():
    data = request.json
    filename = data.get('filename')
    num_lines = data.get('lines')
    page = int(data.get('page', 1))
    page_size = int(data.get('page_size', DEFAULT_PAGE_SIZE))

    if not filename:
        return Response("Filename parameter is required.", status=400)
    
    log_file_path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(log_file_path):
        return Response("Log file not found.", status=404)
    
    try:
        num_lines = int(num_lines) if num_lines else None
    except ValueError:
        num_lines = None

    with open(log_file_path, 'r') as file:
        lines = file.readlines()
        if num_lines:
            lines = lines[-num_lines:]
        
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_lines = lines[start_index:end_index]
        log_content = ''.join(paginated_lines).encode('utf-8')

        if 'gzip' in request.headers.get('Accept-Encoding', ''):
            log_content = compress_response(log_content)
            response = Response(log_content, content_type='text/plain; charset=utf-8')
            response.headers['Content-Encoding'] = 'gzip'
        else:
            response = Response(log_content, content_type='text/plain; charset=utf-8')

        return response

def compress_response(content):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb') as f:
        f.write(content)
    return buf.getvalue()

if __name__ == '__main__':
    app.run(port=8080)
