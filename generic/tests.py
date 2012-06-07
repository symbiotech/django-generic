from django import http
from django.test import TestCase
from django.test.client import RequestFactory
from . import decorators

request_factory = RequestFactory()

@decorators.json_view
def return_dict(request):
    return {'test': 123}

@decorators.json_view
def return_http_response(request):
    return http.HttpResponse('test')

class GenericTest(TestCase):
    def test_json_view_with_dict(self):
        request = request_factory.get('/')
        response = return_dict(request)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.content, '{"test": 123}')

    def test_json_view_with_http_response(self):
        request = request_factory.get('/')
        response = return_http_response(request)
        self.assertTrue('text/html' in response['Content-Type'])
        self.assertEqual(response.content, 'test')
