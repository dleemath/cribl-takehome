import logging
import re
import time
from flask import request, Response
from flask_openapi3 import OpenAPI, Info
import os
import gzip
import io
from flask_cors import CORS
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from config import DevelopmentConfig

# Define OpenAPI Info
info = Info(title='Log File API', version='1.0.0')
app = OpenAPI(__name__, info=info)
app.config.from_object(DevelopmentConfig)
cors = CORS(app)


class LogRequest(BaseModel):
    logpath: str = Field(
        description="Full path of the log file relative to the log directory.")
    num_lines: Optional[int] = Field(
        default=app.config['DEFAULT_RESPONSE_LINES_SIZE'],
        description="Number of lines to return. Default is 1000.")
    offset: Optional[int] = Field(
        default=0, description="Offset in the log file from end. Default is 0.")
    page_size: Optional[int] = Field(
        default=app.config['DEFAULT_PAGE_SIZE'],
        description="Number of lines per page. Default is "
                    "5000.")
    regex: Optional[str] = Field(
        default=None, description="regex pattern for the log lines")
    model_config = ConfigDict(extra="forbid", openapi_extra={
        "example": {
            "logpath": "install.log",
            "num_lines": 50,
            "offset": 0,
            "page_size": 250
        }})


class LogResponseMetaData(BaseModel):
    lines_retrieved: int = Field(default=0,
                                 description="Number of lines retrieved.")
    next_request: Optional[LogRequest] = Field(default=None,
                                               description="Pagination information for the next request.")


class LogResponse(BaseModel):
    data: list = Field(default=[],
                       description="List of lines from the log file.")
    metadata: LogResponseMetaData = Field(
        description="Metadata and information for the next request.")


def read_from_end(file_path,
                  max_chunk_size=app.config['DEFAULT_CHUNK_SIZE'],
                  num_lines=app.config['DEFAULT_RESPONSE_LINES_SIZE'],
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
        # Can't find a newline, so return the whole chunk
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

        # Need to shrink the chunk size if the file size is less than the
        # max chunk size
        chunk_size = max_chunk_size if position > 0 else file_size

        lines = []
        buffer = b''
        start_time = time.time()
        while position >= 0:
            chunk, next_position = read_chunk(f, position, chunk_size)
            buffer = chunk + buffer

            # Split the buffer into lines
            buffer_lines = buffer.splitlines(keepends=True)
            if regex_pattern:
                buffer_lines = [line for line in buffer_lines if
                                regex_pattern.search(
                                    line.decode('utf-8', errors='ignore'))]
            lines = buffer_lines + lines
            read_time = time.time() - start_time
            # Check if we have read enough lines
            if len(lines) > num_lines or read_time > app.config['DEFAULT_READ_TIMEOUT']:
                if read_time > app.config['DEFAULT_READ_TIMEOUT']:
                    logging.warning(
                        f"Timeout reading file {file_path}, partial data returned.")
                resp = lines[-num_lines:][-1::-1]
                total_size = sum(len(line) for line in resp)
                next_offset = offset + total_size
                return resp, next_offset

            if position == 0:
                break

            position = max(next_position - max_chunk_size, 0)

        # If the loop ends without enough lines, return all available lines
        return lines, file_size


def get_next_request(original_request: LogRequest, lines_retrieved: int,
                     offset: int):
    # No next request if we have read enough lines
    if original_request.num_lines <= lines_retrieved:
        return None
    # Construct the next request
    next_request = original_request.model_copy()
    next_request.num_lines = original_request.num_lines - lines_retrieved
    next_request.offset = offset

    return next_request


@app.post('/logs', responses={
    200: LogResponse
})
def get_log_file(body: LogRequest):
    logpath = body.logpath
    num_lines = body.num_lines
    offset = body.offset
    page_size = body.page_size
    regex = body.regex

    if not logpath:
        return Response("Filename parameter is required.", status=400)

    log_file_path = os.path.join(app.config['LOG_DIR'], logpath)
    if not os.path.exists(log_file_path):
        return Response("Log file not found.", status=404)

    try:
        num_lines = int(num_lines) if num_lines else None
    except ValueError:
        num_lines = None

    lines = []
    regex_pattern = re.compile(regex) if regex else None

    # set the max number of lines to read based on the page size and MAX_LINE_SIZE
    max_num_lines_read = min(num_lines, app.config['MAX_LINE_SIZE'], page_size)

    lines, next_offset = read_from_end(
        log_file_path, num_lines=max_num_lines_read, offset=offset,
        regex_pattern=regex_pattern)
    response_lines = [line.decode(
        'utf-8', errors='ignore').strip() for line in lines]
    response_lines_size = len(response_lines)

    next_request = get_next_request(
        original_request=body, lines_retrieved=response_lines_size,
        offset=next_offset)
    log_response_metadata = LogResponseMetaData(
        lines_retrieved=len(response_lines), next_request=next_request)
    log_response = LogResponse(
        data=response_lines, metadata=log_response_metadata)
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
