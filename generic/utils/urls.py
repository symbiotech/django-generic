# TODO: docs

nested_patterns = lambda *x: include(patterns('', *x))
nested_namespace = lambda *x: include(patterns('', *x[1:]), namespace=x[0])
