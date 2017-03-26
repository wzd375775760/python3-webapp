#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 建立ORM(Object, Relational Mapping, 对象关系映射), 此处所有代码都是为此服务的——创建了全局数据库连接池, 
# 封装sql操作, 自定义元类, 定义Model类

#http://blog.csdn.net/haskei/article/details/57075381
import sys
import logging,logging
#一次使用异步 处处使用异步
import asyncio 
import aiomysql

@asyncio.coroutine
def create_pool(loop,**kw):				##**kw是一个dict
	logging.info('create database connection pool...')
	global __pool
	#http://aiomysql.readthedocs.io/en/latest/pool.html
	__pool = yield from aiomysql.create_pool(
        host=kw.get('host','localhost'),    
        port=kw.get('port',3306),      
        user=kw['user'],  
        password=kw['password'],  
        db=kw['db'],  
        charset=kw.get('charset','utf8'),  
        autocommit=kw.get('autocommit',True), #默认自动提交事务，不用手动去提交事务  
        maxsize=kw.get('maxsize',10),  
        minsize=kw.get('minsize',1),  
        loop=loop 
		)
	
@asyncio.coroutine
def destroy_pool():
	global __pool
	if __pool is not None:
		#关闭进程池,The method is not a coroutine,就是说close()不是一个协程，所有不用yield from
		__pool.close()
		#但是wait_close()是一个协程，所以要用yield from,到底哪些函数是协程，上面Pool的链接中都有
		yield from __pool.wait_closed()


@asyncio.coroutine
def select(sql,args,size=None):
	global __pool
	with (yield from __pool) as conn:		#返回连接池信息
		cur = yield from conn.cursor(aiomysql.DictCursor)
		logging.info('select函数开始执行')		
		#A cursor which returns results as a dictionary
		# execute(query, args=None)
		# Coroutine, executes the given operation substituting any markers with the given parameters.
		# For example, getting all rows where id is 5:
		# yield from cursor.execute("SELECT * FROM t1 WHERE id=%s", (5,))
		# Parameters:	
		# query (str) – sql statement
		# args (list) – tuple or list of arguments for sql query
		# Returns int:	
		# number of rows that has been produced of affected
		# print(sql)
		# print(sql.replace('?', '%s'), args)
		print('select函数开始：',sql.replace('?', '%s'),args)
		yield from cur.execute(sql.replace('?', '%s'), args)		#将占位符从sql变为mysql的。
		# yield from cur.execute('select `id`,`email`,`name`,`password` from `User`')
        # yield from cur.execute('select * from user')	
		# print('sise :',size)
		if size:
			rs = yield from cur.fetchmany(size)			#Fetch many rows, just like aiomysql.Cursor.fetchmany().
		else:
			rs = yield from cur.fetchall()				
		yield from cur.close()
		# print('rows returned:%s'%len(rs))
		# print(rs)
		return rs 										#rs是一个list

@asyncio.coroutine
def execute(sql,args):
	# print('execute函数开始:',sql.replace('?', '%s'))
	logging.info('execute函数开始执行')
	with(yield from __pool) as conn:
		try:
			cur = yield from conn.cursor()
			# execute: insert into `User` (`password`,`name`,`email`,`id`) values (%s,%s,%s,%s)  ['321654', 'Tom', '3757757@qq.com', 4]
			logging.info(sql.replace('?', '%s'))
			logging.info(args)
			yield from cur.execute(sql.replace('?', '%s'), args)
			affected = cur.rowcount
			yield from cur.close()
		except BaseExecption as e:
			raise
		return affected  								#affected影响行数

# -*-定义Model的元类  
   
# 所有的元类都继承自type  
# ModelMetaclass元类定义了所有Model基类(继承ModelMetaclass)的子类实现的操作  
   
# -*-ModelMetaclass的工作主要是为一个数据库表映射成一个封装的类做准备：  
# ***读取具体子类(user)的映射信息  
# 创造类的时候，排除对Model类的修改  
# 在当前类中查找所有的类属性(attrs)，如果找到Field属性，就将其保存到__mappings__的dict中，
# 同时从类属性中删除Field(防止实例属性遮住类的同名属性)  
# 将数据库表名保存到__table__中  
   
# 完成这些工作就可以在Model中定义各种数据库的操作方法  
# metaclass是类的模板，所以必须从`type`类型派生：
#通过metaclass类来讲具体的子类（如User）的映射信息读取出来
class ModelMetaclass(type):
	# __new__控制__init__的执行，所以在其执行之前  
    # cls:代表要__init__的类，此参数在实例化时由Python解释器自动提供(例如下文的User和Model)  
    # bases：代表继承父类的集合  
    # attrs：类的方法集合  
	def __new__(cls,name,bases,attrs):
		# 排除model 是因为要排除对model类的修改  
		if name=='Model':
			return type.__new__(cls,name,bases,attrs)
		#获取table名称 .如果存在表名，则返回表名，否则返回 name 
		tableName = attrs.get('__table__',None) or name
		logging.info('found model:%s (table:%s)' % (name,tableName))
		#获取所有的Field和主键名
		mappings = dict()
		fields = []				#field保存的是除主键外的属性名  
		primaryKey = None
		# 这个k是表示字段名
		for k,v in attrs.items():
			if isinstance(v,Field):
				# logging.info('found mapping :%s===>%s' % (k,v))
				mappings[k]=v
				# 这里很有意思 当第一次主键存在primaryKey被赋值 后来如果再出现主键的话就会引发错误  
				if v.primary_key:
					# logging.info('fond primary key %s' % k )
					# print('~'*20,primaryKey)
					 #一个表只能有一个主键，当再出现一个主键的时候就报错
					if primaryKey:
						raise RuntimeError('Duplicate primary key for field :%s' % k)
				#也就是说主键只能被设置一次
					primaryKey = k
				else:
					fields.append(k)
		#如果主键不存在也将会报错，在这个表中没有找到主键，一个表只能有一个主键，而且必须有一个主键
		if not primaryKey:
			raise RuntimeError('Primary key not found')
		# w下面位字段从类属性中删除Field 属性
		for k in mappings.keys():
			attrs.pop(k)
		# 保存除主键外的属性为''列表形式  
        # 将除主键外的其他属性变成`id`, `name`这种形式，关于反引号``的用法，可以参考点击打开链接
		escaped_fields = list(map(lambda f:'`%s`' %f,fields))
		attrs['__mappings__'] = mappings 				#保存属性和列的映射关系
		attrs['__table__'] =tableName
		attrs['__primary_key__']=primaryKey 			#主键属性名
		attrs['__fields__'] = fields  					#除主键外的属性名
		#构造默认的select，insert，update和delete语句
		# print('select `%s`,%s from `%s` ' % (primaryKey,','.join(escaped_fields),tableName))
		attrs['__select__'] = 'select `%s`,%s from `%s` ' % (primaryKey,','.join(escaped_fields),tableName)
		attrs['__insert__'] = 'insert into `%s` (%s,`%s`) values (%s) ' %(tableName,','.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields)+1))
		attrs['__update__'] = 'update `%s` set %s where `%s` = ?' % (tableName,','.join(map(lambda f:'`%s`=? '% (mappings.get(f).name or f),fields)),primaryKey)
		attrs['__delete__'] = 'delete from  `%s` where `%s` = ?' %(tableName,primaryKey)
		return type.__new__(cls,name,bases,attrs)


# 这个函数主要是把查询字段计数 替换成sql识别的?  
# 比如说：insert into  `User` (`password`, `email`, `name`, `id`) values (?,?,?,?)  看到了么 后面这四个问号
def create_args_string(num):
	lol = []
	for n in range(num):
		lol.append('?')
	return(','.join(lol))



# 定义Field类，负责保存(数据库)表的字段名和字段类型 
class Field(object):
	# 表的字段包含名字、类型、是否为表的主键和默认值  
	def __init__(self, name,column_type,primary_key,default):
		self.name = name
		self.column_type = column_type
		self.primary_key = primary_key
		self.default = default

	def __str__(self):
		#返回表名称，字段名，字段类型
		#a.__class__等效于类A。self.__class__.__name__代表类的名称（表名）
		return '<%s,%s,%s>' %(self.__class__.__name__,self.name,self.column_type)

#数据库中的五个存储类型
class StringField(Field):
	"""docstring for StringField"""
	def __init__(self, name = None,primary_key=False,default=None,ddl='varchar(100)'):
		super().__init__(name,ddl,primary_key,default)

#布尔类型不可以当主键
class BooleanField(Field):
	"""docstring for BooleanField"""
	def __init__(self, name=None,default=False):
		super().__init__(name,'Boolean', False,default)

class IntegerField(Field):
	"""docstring for BooleanField"""
	def __init__(self, name=None, primary_key=False, default=0):
		super().__init__(name,'int', primary_key,default)

class FloatField(Field):
	"""docstring for BooleanField"""
	def __init__(self, name=None, primary_key=False, default=0.0):
		super().__init__(name,'float', primary_key,default)

class TextField(Field):
	"""docstring for BooleanField"""
	def __init__(self, name=None, default=0.0):
		super().__init__(name,'text', False,default)
		


# 定义ORM所有映射的基类：Model  
# Model类的任意子类可以映射一个数据库表  
# Model类可以看作是对所有数据库表操作的基本定义的映射  
   
   
# 基于字典查询形式  
# Model从dict继承，拥有字典的所有功能，同时实现特殊方法__getattr__和__setattr__，能够实现属性操作  
# 实现数据库操作的所有方法，定义为class方法，所有继承自Model都具有数据库操作方法  
class Model(dict,metaclass = ModelMetaclass):
	def  __init__(self,**kw):
		super(Model,self).__init__(**kw)

	def __getattr__(self,key):
		try:
			return self[key]
		except Exception as  e:
			raise AttributeError(r"'Model' object has no attribute '%s'" % key)
	def __setattr__(self,key,value):
		self[key]=value

	def getValue(self,key):
		# 这个是默认内置函数实现的
		return getattr(self,key,None)

	def getValueOrDefault(self,key):
		value = getattr(self,key,None)
		if value is None:
			field = self.__mappings__[key]
			if field.default is not None:
				value = field.default() if callable(field.default) else field.default
				logging.debug('using default value for %s :%s' % (key,str(value)))
				setattr(self,key,value)
		return value

	#类方法，谣传一个默认的参数cls 并且有子类继承时，调用该类方法时，传入的类变量cls是子类，而非父类。
	@classmethod
	@asyncio.coroutine
	#根据WHERE条件查找
	def find_all(cls,where=None,args = None,**kw):
		sql = [cls.__select__]
		if where:
			sql.append('where')
			sql.append(where)
		if args in None:
			args = []
		#dict提供get方法，指定不放在时候返回后面第二个参数None
		orderBy = kw.get('orderby',None)
		if orderBy:
			sql.append('order by')
			sql.append(orderBy)
		limit = kw.get('limit',None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit,int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit,tuple) and len(limit) ==2:
				sql.append('?,?')
				args.extend(limit)
			else:
				raise ValueError('Invalid limit value:%s' % str(limit))
		#返回的rs是一个元素为tuple的list
		rs = yield from select(''.join(sql),args)
		#**r是关键字参数，构成一个cls类的列表。即每一条记录对应的类实例
		return [cls(**r) for r in rs]


	#根据WHERE条件查找，但返回的是整数，适用于select count(*)类型的SQL。
	@classmethod
	@asyncio.coroutine
	def findNumber(cls,selectField,where = None,args=None):
		#find number by select and where.
		# num = yield from Blog.findNumber('count(id)')
		logging.info('ORM的findNumber函数：')
		sql = ["select %s _num_ from `%s`" % (selectField, cls.__table__)]
		logging.info(sql)
		if where:
			sql.append('where')
			sql.append(where)
		rs = yield from select(' '.join(sql), args, 1)
		if len(rs) ==0:
			return None
		return rs[0]["_num_"]

	@classmethod
	@asyncio.coroutine
	def find(cls,primarykey):
		#find object by primary key
		#rs是一个list，里面是一个dict
		# 我们之前已将将数据库的select操作封装在了select函数中,以下select的参数依次就是sql, args, size
		rs = yield from select('%s where `%s` = ?' % (cls.__select__,cls.__primary_key__),[primarykey],1)
		if len(rs)==0:
			return None
		#返回一条记录，以dict的形式返回，因为cls的父类继承了dict类
		# **表示关键字参数,我当时还疑惑怎么用到了指针?知识交叉了- -
		# 注意,我们在select函数中,打开的是DictCursor,它会以dict的形式返回结果	
		return cls(**rs[0])

	@classmethod
	@asyncio.coroutine
	def findAll(cls,where = None,args = None,**kw):
		sql = [cls.__select__]
		# 我们定义的默认的select语句是通过主键查询的,并不包括where子句
		# 因此若指定有where,需要在select语句中追加关键字
		if where :
			sql.append('where')
			sql.append(where)
		if args is None:
			args = []
		orderBy = kw.get('orderBy',None)
		if orderBy:
			sql.append('order by')
			sql.append(orderBy)
		limit = kw.get('limit',None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit,int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit,tuple) and len(limit) ==2:
				sql.append(' ?,? ')
				args.extend(limit)
			else:
				raise ValueError('Invalid limit value:%s' % str(limit))		
		rs = yield from select(' '.join(sql),args)
		return [cls(**r) for r in rs]

	# @classmethod
	# @asyncio.coroutine
	# def findNumber(cls,selectField,where=None,args=None):
	# 	# 根据WHERE条件查找，但返回的是整数，适用于select count(*)类型的SQL
	# 	sql = ['select %s _num_ from `%s`' % (selectField,cls.__table__)]
	# 	if where:
	# 		sql.append(' where ')
	# 		sql.append(where)
	# 	rs = yield from select(' '.join(sql),args,1)
	# 	if len(rs) == 0 :
	# 		return None
	# 	return cls(**rs[0])

	@asyncio.coroutine
	def save(self):
		args = list(map(self.getValueOrDefault,self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		print('save函数开始：save:%s' % args)
		rows = yield from execute(self.__insert__,args)
		# print('返回参数rows：',rows)
		if rows !=1:
			print(self.__insert__)
			logging.warning('failed to insert record:affected rows:%s' %rows)

	@asyncio.coroutine
	def update(self):
		#获得的value是要user示例的属性值，即传入的name，email，password值
		args = list(map(self.getValue,self.__fields__))
		args.append(self.getValue(self.__primary_key__))
		print('执行update：',args)
		print(self.__update__)
		rows = yield from execute(self.__update__,args)
		if rows !=1:
			logging.warning('failed to update record:affected rows: %s' % rows)

	@asyncio.coroutine
	def remove(self):
		args = [self.getValue(self.__primary_key__)]
		rows = yield from execute(self.__delete__,args)
		if rows !=1:
			logging.warning('failed to delete by primary key:affected rows: %s' % rows)
