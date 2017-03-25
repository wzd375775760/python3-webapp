#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 全部的handlers及一些辅助函数, 包括验证用户权限, 检查cookie等

import time
import re
import json
import logging
import hashlib
import base64
import asyncio
import markdown2
from aiohttp import web
from coroweb import get, post # 导入装饰器,这样就能很方便的生成request handler
from models import Comment,User,Blog, next_id
from apis import APIResourceNotFoundError, APIValueError, APIError, APIPermissionError, Page
from config import configs
logging.basicConfig(level=logging.INFO,
					format = "%(asctime)s %(message)s",
					datefmt = "[%Y-%m-%d %H:%M:%S]")

# 此处所列所有的handler都会在app.py中通过add_routes自动注册到app.router上
# 因此,在此脚本尽情地书写request handler即可
COOKIE_NAME = "awesession"	#cookie名，用于设置cookie
_COOKIE_KEY = configs.session.secret 	#cookie密钥，作为加密cookie的原始字符串的一部分

#匹配邮箱与加密后面的正则表达式
_RE_EMAIL=re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1=re.compile(r'[0-9a-f]{40}$')

#验证用户身份
def check_admin(request):
	logging.info('check_admin权限：')
	logging.info(request.__user__.admin)
	if request.__user__ is None or not request.__user__.admin:
		raise APIPermissionError()

#取得页码
def get_page_index(page_str):
	p = 1
	try:
		p = int(page_str)
	except ValueError as e:
		pass
	if p<1:
		p = 1
	return p

#文本转html
def text2html(text):
	'''文本转html'''
	# 先用filter函数对输入的文本进行过滤处理: 断行,去首尾空白字符
	# 再用map函数对特殊符号进行转换,在将字符串装入html的<p>标签中
	lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
	# lines是一个字符串列表,将其组装成一个字符串,该字符串即表示html的段落
	return ''.join(lines)

#通过用户信息计算加密cookie
def user2cookie(user,max_age):
	# build cookie string by: id-expires-sha1
	expires = str(int(time.time() + max_age))
	#expires(失效时间)是当前时间加上cookie最大存活时间的字符串
	#利用用户id,加密后的密码,失效时间,加上cookie密钥,组合成待加密的原始字符串
	s = "%s-%s-%s-%s" % (user.id,user.passwd,expires,_COOKIE_KEY)
	# 生成加密的字符串,并与用户id,失效时间共同组成cookie
	L = [user.id,expires,hashlib.sha1(s.encode("utf-8")).hexdigest()]
	return "-".join(L)

#解密cookie
@asyncio.coroutine
def cookie2user(cookie_str):
	if not cookie_str:
		return None
	try:
		#先通过‘-’拆分，得到用户id，失效时间，加密字符串
		L = cookie_str.split('-')
		if len(L) !=3:
			return None
		uid,expires,sha1 = L
		if int(expires) <time.time():	#失效时间小于当前时间，说明cookie已失效
			return None
		user = yield from User.find(uid)	# 在拆分得到的id在数据库中查找用户信息
		if user is None:
			return None
		# 利用用户id,加密后的密码,失效时间,加上cookie密钥,组合成待加密的原始字符串
		# 再对其进行加密,与从cookie分解得到的sha1进行比较.若相等,则该cookie合法
		s = '%s-%s-%s-%s' % (uid,user.passwd,expires,_COOKIE_KEY)
		if sha1 !=hashlib.sha1(s.encode('utf-8')).hexdigest():
			logging.info('invalid sha1')
			return None
		# 以上就完成了cookie的验证,过程非常简单,但个人认为效率不高
		# 验证cookie,就是为了验证当前用户是否仍登录着,从而使用户不必重新登录
		# 因此,返回用户信息即可	
		user.passwd = '******'
		return user			
	except Exception as e:
		logging.exception(e)
	return None		
	
#首页get请求的处理
@get('/')
def index(*,page='1'):
	page_index = get_page_index(page)
	num = yield from Blog.findNumber('count(id)')
	page = Page(num,page_index)
	if num == 0:
		blogs = []
	else:
		blogs = yield from Blog.findAll(orderBy = 'created_at desc',limit = (page.offset,page.limit))
	# 返回一个字典, 其指示了使用何种模板,模板的内容
	# app.py的response_factory将会对handler的返回值进行分类处理
	return {
		'__template__':'blogs.html',
		'page':page,
		'blogs':blogs 	# 参数blogs将在jinja2模板中被解析
	}

#API:获取用户信息
@get('/api/users')
def api_get_users(*,page='1'):
	page_index = get_page_index(page)
	num = yield from User.findNumber("count(id)")
	p= Page(num,page_index)
	if num==0:
		return dict(page=p,users=())
	users = yield from User.findAll(orderBy="created_at desc")
	for u in users:
		u.paasswd="******"
	 # 以dict形式返回,并且未指定__template__,将被app.py的response factory处理为json
	print('api/user')	
	return dict(page=p,users=users)	

#API:创建用户_post
@post('/api/users')
def api_register_user(*,name,email,passwd):
	#验证输入的正确性
	print('调用api.....')
	logging.info(name)
	logging.info(email)
	logging.info(passwd)
	if not name or not name.strip():
		raise APIValueError("name")
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError("email")
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError("passwd")
	#查看是否存在该email
	# mysql parameters are listed in list
	users = yield from User.findAll('email=?',[email])	
	if len(users) >0:
		raise APIError('register:failed','email','Email is already in use')

	# 数据库内无相应的email信息,说明是第一次注册
	uid = next_id()
	sha1_passwd = '%s:%s' % (uid,passwd)
	# 将user id与密码的组合赋给sha1_passwd变量
    # 创建用户对象, 其中密码并不是用户输入的密码,而是经过复杂处理后的保密字符串
    # unicode对象在进行哈希运算之前必须先编码
    # sha1(secure hash algorithm),是一种不可逆的安全算法.这在一定程度上保证了安全性,因为用户密码只有用户一个人知道
    # hexdigest()函数将hash对象转换成16进制表示的字符串
    # md5是另一种安全算法
    # Gravatar(Globally Recognized Avatar)是一项用于提供在全球范围内使用的头像服务。只要在Gravatar的服务器上上传了你自己的头像，便可以在其他任何支持Gravatar的博客、论坛等地方使用它。此处image就是一个根据用户email生成的头像
	user = User(id=uid,name=name.strip(),email=email,passwd = hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),image = "http://www.gravatar.com/avatar/%s?d=mm&s=120" % hashlib.md5(email.encode('utf-8')).hexdigest())
	yield from user.save()

	# 这其实还是一个handler,因此需要返回response. 此时返回的response是带有cookie的响应
	r=web.Response()
	# 刚创建的的用户设置cookiei(网站为了辨别用户身份而储存在用户本地终端的数据)
	# http协议是一种无状态的协议,即服务器并不知道用户上一次做了什么.
	# 因此服务器可以通过设置或读取Cookies中包含信息,借此维护用户跟服务器会话中的状态
	# user2cookie设置的是cookie的值
	# max_age是cookie的最大存活周期,单位是秒.当时间结束时,客户端将抛弃该cookie.之后需要重新登录

	r.set_cookie(COOKIE_NAME,user2cookie(user,600),max_age=600,httponly=True)	# 设置cookie最大存会时间为10min
	# r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)  #86400s=24h
	user.passwd = '******'	#修改密码外部显示为*
	# 设置content_type,将在data_factory中间件中继续处理
	r.content_type='application/json'
	# json.dumps方法将对象序列化为json格式
	r.body = json.dumps(user,ensure_ascii=False).encode('utf-8')
	return r

#API：用户验证
@post('/api/authenticate')
def authenticate(*,email,passwd):	#通过邮箱密码验证登录
	if not email:
		raise APIValueError('email','Invalid email')
	if not passwd:
		raise APIValueError('passwd','Invalid passwd')
	users = yield from User.findAll('email=?',[email])
	if len(users) == 0 :
		raise APIValueError('email','Email not exits')
	user = users[0]	# 取得用户记录.事实上,就只有一条用户记录,只不过返回的是list
	# 验证密码
	# 数据库中存储的并非原始的用户密码,而是加密的字符串
	# 我们对此时用户输入的密码做相同的加密操作,将结果与数据库中储存的密码比较,来验证密码的正确性
	# 以下步骤合成为一步就是:sha1 = hashlib.sha1((user.id+":"+passwd).encode("utf-8"))
	# 对照用户时对原始密码的操作(见api_register_user),操作完全一样
	sha1 = hashlib.sha1()
	sha1.update(user.id.encode('utf-8'))
	sha1.update(b':')
	sha1.update(passwd.encode('utf-8'))
	if user.passwd!=sha1.hexdigest():
		raise APIValueError('passwd','Invalid password')
	#用户登录之后，同样设置一个cookie，与注册用户部分的代码完全一样
	r = web.Response()
	r.set_cookie(COOKIE_NAME,user2cookie(user,600),max_age=600,httponly = True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user,ensure_ascii=False).encode('utf-8')
	logging.info(r)
	return r	

#API:获取blog_get
@get('/api/blogs')
def api_blogs(*,page='1'):
	page_index = get_page_index(page)
	num = yield from Blog.findNumber('count(id)')	# num为博客总数
	p = Page(num,page_index)		# 创建page对象
	if num ==0:
		return dict(page=p, blogs=())	# 若博客数为0,返回字典,将被app.py的response中间件再处理
	# 博客总数不为0,则从数据库中抓取博客
	# limit强制select语句返回指定的记录数,前一个参数为偏移量,后一个参数为记录的最大数目	
	blogs = yield from Blog.findAll(orderBy='created_at desc',limit = (p.offset,p.limit))
	return dict(page=p,blogs=blogs)	

#API:获取单条博客
@get('/api/blogs/{id}')
def api_get_blog(*,id):
	blog = yield from Blog.find(id)
	return blog

#博客详情页面
@get('/blog/{id}')
def get_blog(id):
	logging.info('/blog/{id}函数开始：')
	logging.info(id)
	blog = yield from Blog.find(id)
	#从数据库拉取指定blog的全部评论,按时间降序排序,即最新的排在最前
	comments = yield from Comment.findAll('blog_id=?',[id],orderBy='created_at desc')
	for c in comments:
		c.html_content = text2html(c.content)
	blog.html_content = markdown2.markdown(blog.content)	# blog是markdown格式,将其转换为html格式
	return {
		'__template__':'blog.html',
		'blog':blog,
		'comments':comments
	}	

#API:创建blog_post
@post('/api/blogs')
def api_create_blog(request,*,name,summary,content):
	check_admin(request)	#检查用户权限
	if not name or not name.strip():
		raise APIValueError('name','name connot be empty')
	if not summary or not summary.strip():
		raise APIValueError('summary','summary cannot be empty')
	if not content or not content.strip():
		raise APIValueError('content','content cannot be empty')
	#创建博客对象
	logging.info('调用api')
	logging.info(name)
	logging.info(request.__user__.id)
	logging.info(request)
	blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
	yield from blog.save()
	return blog

#写博客的页面
@get('/manage/blogs/create')
def manage_create_blog():
	return {
		'__template__':'manage_blog_edit.html',
		'id':'',
		'action':'/api/blogs'
		# id的值将传给js变量I
		# action的值也将传给js变量action
		# 将在用户提交博客的时候,将数据post到action指定的路径,此处即为创建博客的api
	}

# 修改博客的页面
@get('/manage/blogs/edit')
def manage_edit_blog(*,id):
	return {
		'__template__':'manage_blog_edit.html',
		'id':id,	# id的值将传给js变量
		# 将在用户提交博客的时候,将数据post到action指定的路径,此处即为创建博客的api
		'action':'/api/blogs/%s' % id
	}

# 管理博客的页面
@get('/manage/blogs')
def manage_blogs(*,page='1'):
	return {
		'__template__':'manage_blogs.html',
		'page_index':get_page_index(page)
	}

#API:删除博客
@post('/api/blogs/{id}/delete')
def api_delete_blog(request,*,id):
	check_admin(request)
	blog=yield from Blog.find(id);
	yield from blog.remove()
	return dict(id=id)


#API：创建评论
@post('/api/blogs/{id}/comments')
def api_create_comment(id,request,*,content):
	user = request.__user__
	logging.info('获取blog信息：')
	logging.info(user)
	if user is None:
		raise APIPermissionError('Please signin first.')
	if not content or not content.strip():
		raise APIError('content','content cannot be empty')
	blog = yield from Blog.find(id)
	if blog is None:
		raise APIResourceNotFoundError('Blog','No suck a blog.')
	
	logging.info(blog.id)
	comment = Comment(user_id=user.id,user_name=user.name,user_image=user.image,blog_id=blog.id,content=content.strip())			
	yield from comment.save()
	return comment 

#管理评论的页面
@get('/manage/comments')
def manage_comments(*,page='1'):
	return {
		'__template__':'manage_comments.html',
		'page_index':get_page_index(page)	#通过page_index来显示分页
	}

#API:获取评论
@get('/api/comments')
def api_comments(*,page='1'):
	page_index = get_page_index(page)
	num = yield from Comment.findNumber('count(id)')
	p=Page(num,page_index)
	if num==0:
		return dict(page=p,comments=())
	comments = yield from Comment.findAll(orderBy='created_at desc',limit=(p.offset,p.limit))
	return dict(page=p,comments=comments)	# 返回字典,以供response中间件处理

#API：删除评论
@post('/api/comments/{id}/delete')
def api_delete_comments(id,request):
	check_admin(request)
	comment = yield from Comment.find(id)
	if comment is None:
		raise APIResourceNotFoundError('comment','No suck a Comment')
	yield from comment.remove()
	return dict(id=id)

#管理用户的页面
@get('/manage/users')
def manage_users(*,page='1'):
	return {
		'__template__':'manage_users.html',
		'page_index':get_page_index(page)
	}

#管理重定向
@get('/manage/')
def manage():
	return 'redirect:/manage/comments'

#返回注册页面
@get('/register')
def register():
	return {
		'__template__':'register.html'
	}

#返回登陆页面
@get('/signin')
def signin():
	return {
		'__template__':'signin.html'
	}	

#用户登出
@get('/signout')
def signout(request):
	referer = request.headers.get('Referer')
	r = web.HTTPFound(referer or '/')
	r.set_cookie(COOKIE_NAME,'-deleted-',max_age=0,httponly=True)
	logging.info('user signed out.')
	return r			