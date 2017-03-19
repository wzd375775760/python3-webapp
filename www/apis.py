#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 定义了APIError类与Page类, 分别用于api错误提示与页面管理
'Json API definition'



class APIError(Exception):
	"""定义APIError基类，集成自exception"""
	def __init__(self, error,data='',message = ''):
		super(APIError, self).__init__(message)
		self.error = error
		self.data = data
		self.message = message
