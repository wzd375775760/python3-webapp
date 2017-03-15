import sys
import asyncio
import orm
from models import User,Blog,Comment

if __name__=='__main__':
	loop = asyncio.get_event_loop()
	@asyncio.coroutine
	def test():
		yield from orm.create_pool(loop=loop,host = 'localhost',port=3306,user='root',password='password',db='mypython3')
		user = User(name='Jack',email='Jack@163.com',password='1234567890',image='about:blank')
		# user.save()
		r = yield from user.findAll()	
		print(r)

		yield from orm.destroy_pool()

	loop.run_until_complete(test())
	loop.close()
	if loop.is_closed():
		sys.exit(0)	


# def test():
# 	loop = asyncio.get_event_loop()

#     yield from orm.create_pool(loop = loop,host = 'localhost',port = 3306,user='root',password = 'password',db='mypython3')
#     user = User(name='Jack',email='Jack@163.com',password='1234567890',image='about:blank')
#     	# r = yield from user.findAll()		
#     yield from user.save()  
#         #ield from user.update()  
#         #yield from user.delete()  
#         # r = yield from User2.find(8)  
#         # print(r)  
#         # r = yield from User2.findAll()  
#         # print(1, r)  
#         # r = yield from User2.findAll(name='sly')  
#         # print(2, r)  
#     # yield from destory_pool()

# for x in test():
# 	pass
