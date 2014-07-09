# papa

## Description
**papa** is a library for creating sockets and launching processes from a stable
parent process.

## Dependencies
It is tested under following Python versions:

- 2.6
- 2.7
- 3.3
- 3.4


## Installation
You can install it from Python Package Index (PyPI):

	$ pip install papa

## Usage
```python
from papa import Papa

p = Papa()
print(p.sockets())
print(p.make_socket('uwsgi', port=8080))
print(p.sockets())
```
