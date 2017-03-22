#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 定义了APIError类与Page类, 分别用于api错误提示与页面管理
'Json API definition'

import json
import logging
import inspect	# the module provides several useful functions to help get information about live objects, such as modules, classes, methods, functions.
import functools 	# 该模块提供有用的高阶函数.总的来说,任何callable对象都可视为函数

#page对象，用于储存分页信息
class Page(object):
	"""docstring for Page"""
	def __init__(self, item_count,page_index = 1,page_size=10):
		'''init Pagination by item_count, page_index, page_size
		item_count - 博客总数
		page_index - 页码
		page_size - 一个页面最多显示博客的数目'''
		self.item_count = item_count #从数据库中查询博客的总数获得
		self.page_size=page_size	#可自定义或使用默认值
		# logging.info(item_count)
		# 页面数目,由博客总数与每页的博客数共同决定
		# item_count 不能被page_size整除时,最后一页的博客数目不满page_size,但仍需独立设立一页
		# 以下式子等价与 math.ceil(item_count / page_size)
		self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
		# offset为偏移量,limit为限制数目,将被用于获取博客的api
		# 比如共有98篇博客,page_size=10, 则page_count=10.
		# 当前page_index=9,即这一页的博客序号(假设有)为81-90.此时offset=80
		if(item_count == 0) or (page_index > self.page_count):
			#没有博客或页面出错，将offset，limit置为0，页码置为1
			self.offset = 0
			self.limit = 0 
			self.page_index = 0
		else:	#有博客，并且制定页码未超出页面总数的
			self.page_index = page_index		#页码为制定页码
			self.offset = self.page_size * (page_index - 1)			#页面偏移量
			self.limit = self.page_size			#页面的博客限制数与页面大小一致
		self.has_next = self.page_index <self.page_count 		# 页码小于页面总数,说有有下页
		self.has_previous = self.page_index > 1	 	# > 若页码大于1,说明有前页

	def __str__(self):
		return "item_count:%s,page_count:%s,page_index:%s,page_size:%s,offset:%s,limit:%s" % (self.item_count,self.page_count,self.page_index,self.page_size,self.offset,self.limit)

	__repr__ = __str__


class APIError(Exception):
	"""定义APIError基类，继承自exception"""
	def __init__(self, error,data='',message = ''):
		super(APIError, self).__init__(message)
		self.error = error
		self.data = data
		self.message = message

class APIValueError(APIError):
	'''
	定义APIValueError类
	表明输入的值错误或不合法.
	data属性指定为输入表单的错误域
	'''
	def __init__(self,field,message=""):
		super(APIValueError,self).__init__("value:invalid",field,message)

class APIResourceNotFoundError(APIError):
	'''
	定义APIResourceNotFoundError类
	表明找不到指定资源.
	data属性指定为资源名
	'''
	def __init__(self,field,message=""):
		super(APIResourceNotFoundError,self).__init__("value:notfound",field,message)	

class APIPermissionError(APIError):
	'''
	定义APIPermissionError类
	表明没有权限
	'''
	def __init__(self,message=""):
		super(APIPermissionError,self).__init__("value:forbidden","permission",message)			
