#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#http://www.qiangtaoli.com/bootstrap/blog/001466339384240fec2e91483ac41bdb5352c1034be03e9000
import asyncio,os,inspect,logging,functools

from urllib import parse

from aiohttp import web


from apis import APIError

def get(path):
	#定义装饰器@get('/path')
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args,**kw):
			return func(*args,**kw)
		wrapper.__method__='GET'
		wrapper.__route__=path
		return wrapper
	return decorator

def post(path):
	#定义装饰器@post('/path')
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args,**kw):
			return func(*args,**kw)
		wrapper.__method__='POST'
		wrapper.__route__=path
		return wrapper
	return decorator