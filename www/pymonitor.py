#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os,sys,time,subprocess	# 该模块提供了派生新进程的能力

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def log(s):
	print('[Monitor] %s' % s)

# 自定义的文件系统事件处理器
class MyFileSystemEventHander(FileSystemEventHandler):
	"""docstring for MyFileSystemEventHander"""
	# 初始化函数,将指定函数绑定到处理器的restart属性上
	def __init__(self, fn):
		super(MyFileSystemEventHander, self).__init__()
		self.restart = fn

	# 覆盖on_any_event方法
	# on_any_event(event)捕获所有事件, 文件或目录的创建, 删除, 修改等
	def on_any_event(self,event):
		# 此处只处理python脚本的事件
		if event.src_path.endswith('.py'):
			log('Python source file changed:%s' % event.src_path)
			self.restart()

command=['echo','ok']
process=None

def kill_process():
	global process
	if process:
		log('Kill process [%s] ...' %process.pid)
		 # process指向一个Popen对象,在start_process函数中被创建
		 # 通过发送一个SIGKILL给子程序, 来杀死子程序. SIGKILL信号将不会储存数据, 此处也不需要
		 # wait(timeout=None),等待进程终止,并返回一个结果码. 该方法只是单纯地等待, 并不会调用方法来终止进程, 因此需要kill()方法
		process.kill()
		process.wait()
		log('Process ended with code %s.' % process.returncode)
		process=None

def start_process():
	global process,command
	log('start process %s ...' % ' '.join(command))
	 # subprocess.Popen是一个构造器, 它将在一个新的进程中执行子程序
	 # command是一个list, 即sequence. 此时, 将被执行的程序应为序列的第一个元素, 此处为python3
	process=subprocess.Popen(command, stdin = sys.stdin, stdout = sys.stdout, stderr = sys.stderr)

def restart_process():
	kill_process()
	start_process()		

def start_watch(path,callback):
	observer = Observer()
	# 为监视器对象安排时间表, 即将处理器, 路径注册到监视器对象上
	# 重启进程函数绑定到处理器的restart属性上
	# recursive=True表示递归, 即当前目录的子目录也在被监视范围内
	observer.schedule(MyFileSystemEventHander(restart_process),path,recursive=True)
	observer.start()
	log('Watching diretory %s...' % path)
	# 启动进程, 通过调用subprocess.Popen方法启动一个python3子程序的进程
	start_process()
	try:
		while True:
			time.sleep(0.5)
	except KeyboardInterrupt:
		observer.stop()
	observer.join()

if __name__=='__main__':
	argv = sys.argv[1:]		# sys.argv[0]表示当前被执行的脚本
	if not argv:
		print('Usage:./pymonitor your-script.py')
		exit(0)
	# 检查输入参数, 若第一个参数非"python3", 则添加"python3"
	if argv[0]!='python':
		argv.insert(0,'python')
	command = argv
	path = os.path.abspath('.')
	start_watch(path,None)			
		