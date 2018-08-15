import time as tm
import numpy as np

nx = 1000000
nk = 10

start_time = tm.time()
for k in range(nk):
    x = [0.0 for i in range(nx)]
end_time = tm.time()
time_per_k = (end_time - start_time) / float(nk)
print "time per k: %12.4e" % time_per_k
x = None

start_time = tm.time()
x = np.zeros(shape=nx)
for k in range(nk):
    #x = np.array([0.0 for i in range(nx)])
    x = np.zeros(shape=nx)
    #x[:] = [0.0 for i in range(nx)]
end_time = tm.time()
time_per_k = (end_time - start_time) / float(nk)
print "time per k: %12.4e" % time_per_k
x = None
