import logging
import re
from flask import Flask, json, request, jsonify, Response
from flask_openapi3 import OpenAPI, Info
import os
import gzip
import io
from flask_cors import CORS
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


# Log directory and default page size
LOG_DIR = "/Users/yifangl/develop/job24/cribl-takehome/testdata/"
DEFAULT_PAGE_SIZE = 5000
DEFAULT_RESPONSE_LINES_SIZE = 1000


class LogRequest(BaseModel):
    logpath: str = Field(
        description="Full path of the log file relative to the log directory.")
    lines: Optional[int] = Field(default=DEFAULT_RESPONSE_LINES_SIZE,
                                 description="Number of lines to return. Default is 1000.")
    offset: Optional[int] = Field(
        default=0, description="Offset in the log file from end. Default is 0.")
    page_size: Optional[int] = Field(
        default=DEFAULT_PAGE_SIZE, description="Number of lines per page. Default is 5000.")
    regex: Optional[str] = Field(
        default=None, description="regex pattern for the log lines")
    model_config = ConfigDict(extra="forbid", openapi_extra={
        "example": {
            "logpath": "install.log",
            "lines": 50,
            "offset": 0,
            "page_size": 250
        }})


class LogResponse(BaseModel):
    lines: list
    offset: int


# Define OpenAPI Info
info = Info(title='Log File API', version='1.0.0')
app = OpenAPI(__name__, info=info)
cors = CORS(app)


def read_from_end(file_path,
                  max_chunk_size=1024*1024,
                  num_lines=DEFAULT_RESPONSE_LINES_SIZE,
                  offset=0,
                  regex_pattern=None):
    # A helper function to read the chunk and manage line boundaries
    def read_chunk(f, position, size):
        # Move the pointer to the start position
        f.seek(position)
        # Read a chunk of data from the file
        chunk = f.read(size)
        # Find the last newline character in the chunk
        last_newline = chunk.decode('utf-8', errors='ignore').rfind('\n')
        if last_newline == -1:
            return chunk, position
        else:
            # Adjust the position to read the next chunk correctly
            return chunk[:last_newline + 1], position + last_newline + 1

    with open(file_path, 'rb') as f:
        # Move to the end of the file
        f.seek(-offset, os.SEEK_END)
        file_size = f.tell()
        position = max(file_size - max_chunk_size, 0)

        lines = []
        buffer = b''

        while position >= 0:
            chunk, next_position = read_chunk(f, position, max_chunk_size)
            buffer = chunk + buffer

            # Split the buffer into lines
            buffer_lines = buffer.splitlines(keepends=True)
            if regex_pattern:
                buffer_lines = [line for line in buffer_lines if regex_pattern.search(
                    line.decode('utf-8', errors='ignore'))]
            lines = buffer_lines + lines

            # Check if we have read enough lines
            if len(lines) > num_lines:
                resp = lines[-num_lines:][-1::-1]
                total_size = sum(len(line) for line in lines)
                next_offset = file_size - position + total_size
                return resp, next_offset

            if position == 0:
                break

            position = max(next_position - max_chunk_size, 0)

        # If the loop ends without enough lines, return all available lines
        return lines, file_size


@app.post('/logs',responses={
             200: LogResponse 
         })
def get_log_file(body: LogRequest):
    """Get log file content
    Retrieves a specified number of lines from the end of a log file.

    Parameters:
        body (LogRequest): The request body containing the log file path, number of lines to retrieve,
                           offset, page size, and regex pattern.

    Returns:
        Response: The response containing the retrieved lines and the next offset. If the filename parameter
                  is missing or the log file is not found, a 400 or 404 response is returned respectively.

    Raises:
        ValueError: If the number of lines parameter is not an integer.

    Note:
        - The log file path is relative to the LOG_DIR directory.
        - If the number of lines parameter is not provided, all available lines are returned.
        - If the offset parameter is provided, the lines are retrieved from that offset.
        - If the page_size parameter is provided, the response is compressed using gzip.
    """
    
    filename = body.logpath
    num_lines = body.lines
    offset = body.offset
    page_size = body.page_size
    regex = body.regex

    if not filename:
        return Response("Filename parameter is required.", status=400)

    log_file_path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(log_file_path):
        return Response("Log file not found.", status=404)

    try:
        num_lines = int(num_lines) if num_lines else None
    except ValueError:
        num_lines = None

    lines = []
    regex_pattern = re.compile(regex) if regex else None
    lines, next_offset = read_from_end(
        log_file_path, num_lines=num_lines, offset=offset, regex_pattern=regex_pattern)
    response_lines = [line.decode(
        'utf-8', errors='ignore').strip() for line in lines]
    log_response = LogResponse(lines=response_lines, offset=next_offset)
    response = log_response.model_dump_json()
    if 'gzip' in request.headers.get('Accept-Encoding', ''):
        response = compress_response(response.encode('utf-8'))
        response = Response(
            response, content_type='application/json; charset=utf-8')
        response.headers['Content-Encoding'] = 'gzip'
    else:
        response = Response(
            response, content_type='application/json; charset=utf-8')

    return response


def compress_response(content):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb') as f:
        f.write(content)
    return buf.getvalue()


if __name__ == '__main__':
    app.run(port=8080)
