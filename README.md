# Simple Log Server


## Overview
A simple REST API server to get lines from a given log.

## Run the Server

Server can be configured with `config.py`
```python
class Config(object):
    TESTING = False
    DEFAULT_PAGE_SIZE = 1000
    DEFAULT_RESPONSE_LINES_SIZE = 1000
    DEFAULT_CHUNK_SIZE = 1024 * 1024
    MAX_LINE_SIZE = 200000
    DEFAULT_READ_TIMEOUT = 5
```
Install packages:
```bash
 pip install -r requirements.txt        
```


Development Mode:
```bash
python log_server.py -v
 * Serving Flask app 'log_server'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:8080
Press CTRL+C to quit
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: 117-267-318
```

Production Mode:
```bash
# run with 4 gunicorn workers
gunicorn -w 4 'log_server:app'                                                                                                                            
[2024-06-19 13:57:17 -0700] [87141] [INFO] Starting gunicorn 22.0.0
[2024-06-19 13:57:17 -0700] [87141] [INFO] Listening at: http://127.0.0.1:8000 (87141)
[2024-06-19 13:57:17 -0700] [87141] [INFO] Using worker: sync
[2024-06-19 13:57:17 -0700] [87351] [INFO] Booting worker with pid: 87351
[2024-06-19 13:57:17 -0700] [87395] [INFO] Booting worker with pid: 87395
```

## Usage
### **`POST`** _/logs_

> Get log file content : _Retrieves a specified number of lines from the end of a log file._
#### Request
> Request body schema `application/json`

> Sample LogRequest object

```json
{
  "logpath": "install.log",
  "num_lines": 50,
  "offset": 0,
  "page_size": 250
}
```

-`logpath`: `required` `string` 
Full path of the log file relative to the log directory.

-`num_lines`:	
`optional` `integer` `default:1000`
Number of lines to return. Default is 1000.

-`offset`:	`optional` `integer` `default:0`
Offset in bytes from the end of the log file. Default is 0.

-`page_size`: `optional` `integer` `default:1000`
Number of lines per page. Default is 5000.

-`regex`: `optional` `string` regex pattern to filter the log lines

#### Response
> Response body schema `application/json`

> Sample LogResponse object

```json
{
  "data": [],
  "metadata": {
    "lines_retrieved": 0,
    "next_request": {
      "logpath": "string",
      "num_lines": 1000,
      "offset": 0,
      "page_size": 1000,
      "regex": "string"
    }
  }
}
```
-`data`: `list` 
list of log lines returned in reversed order.
-`metadata`: `dict` 
include number of lines retrieved and a LogRequest object for the next page.

## Design Details

### Using POST to avoid URL encode length limit
Choose `POST` instead of `GET` and query form. The `logpath` could be long and/or include some special characters. 

### Pagination on demand
If the required `num_lines` is bigger than `page_size` or `MAX_LINE_SIZE`, request body for the next page will be included in the response so the client can read from the next request until all `num_lines` are retrieved.

### Handle large files
Log will will be read in small chunks with 1mb `DEFAULT_CHUNK_SIZE`, also introduced a timeout (default value is 5s) in file reading. 


## OpenAPI Doc
After starting the server, OpenAPI can be accessed from `http://127.0.0.1:8000/openapi/redoc`

## Testing
E2E tests are defined in `test_log_server.py`. Tests can be run with `PyTest`

```bash
python -m pytest test_log_server.py -v                                                                    


============================================================================================================ test session starts =============================================================================================================
platform darwin -- Python 3.12.1, pytest-8.2.2, pluggy-1.5.0 -- /Users/yifangl/.pyenv/versions/venv_c/bin/python
cachedir: .pytest_cache
rootdir: /Users/yifangl/develop/job24/cribl-takehome
plugins: flask-1.3.0
collected 6 items

test_log_server.py::test_get_log_file_no_filename PASSED                                                                                                                                                                               [ 16%]
test_log_server.py::test_get_log_file_not_found PASSED                                                                                                                                                                                 [ 33%]
test_log_server.py::test_get_log_file_success PASSED                                                                                                                                                                                   [ 50%]
test_log_server.py::test_get_log_file_with_regex PASSED                                                                                                                                                                                [ 66%]
test_log_server.py::test_get_log_file_with_next_request PASSED                                                                                                                                                                         [ 83%]
test_log_server.py::test_get_log_file_with_gzip PASSED    
```

## TODO
The file offset approach could have some inconsistency issue e.g. log file changed between requests. 