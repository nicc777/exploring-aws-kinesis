```text
            $$$$$$$\        $$$$$$$$\       $$$$$$$\        $$$$$$\        $$$$$$\                           
            $$  __$$\       $$  _____|      $$  __$$\       \_$$  _|      $$  __$$\                          
            $$ |  $$ |      $$ |            $$ |  $$ |        $$ |        $$ /  \__|                         
            $$$$$$$  |      $$$$$\          $$ |  $$ |        $$ |        \$$$$$$\                           
            $$  __$$<       $$  __|         $$ |  $$ |        $$ |         \____$$\                          
            $$ |  $$ |      $$ |            $$ |  $$ |        $$ |        $$\   $$ |                         
            $$ |  $$ |      $$$$$$$$\       $$$$$$$  |      $$$$$$\       \$$$$$$  |                         
            \__|  \__|      \________|      \_______/       \______|       \______/                          
                                                                                                 
                                                                                                 
                                                                                                 
$$$$$$$$\                                         $$\                                    $$\     
$$  _____|                                        \__|                                   $$ |    
$$ |      $$\   $$\  $$$$$$\   $$$$$$\   $$$$$$\  $$\ $$$$$$\$$$$\   $$$$$$\  $$$$$$$\ $$$$$$\   
$$$$$\    \$$\ $$  |$$  __$$\ $$  __$$\ $$  __$$\ $$ |$$  _$$  _$$\ $$  __$$\ $$  __$$\\_$$  _|  
$$  __|    \$$$$  / $$ /  $$ |$$$$$$$$ |$$ |  \__|$$ |$$ / $$ / $$ |$$$$$$$$ |$$ |  $$ | $$ |    
$$ |       $$  $$<  $$ |  $$ |$$   ____|$$ |      $$ |$$ | $$ | $$ |$$   ____|$$ |  $$ | $$ |$$\ 
$$$$$$$$\ $$  /\$$\ $$$$$$$  |\$$$$$$$\ $$ |      $$ |$$ | $$ | $$ |\$$$$$$$\ $$ |  $$ | \$$$$  |
\________|\__/  \__|$$  ____/  \_______|\__|      \__|\__| \__| \__| \_______|\__|  \__|  \____/ 
                    $$ |                                                                         
                    $$ |                                                                         
                    \__|                     
```

> Logo created with [http://patorjk.com/software/taag/](http://patorjk.com/software/taag/#p=display&f=Big%20Money-nw&t=R%20E%20D%20I%20S%0AExperiment)

# Local Experiment Setup

> _**Note**_: I am also using this opportunity to experiment with [Podman](https://podman.io/) as a replacement for Docker, since the latter is going all commercial with less and less "opensourceness".

The official image I will be using is from Docker Hub: https://hub.docker.com/_/redis

Pulling the image:

```shell
podman pull docker.io/library/redis
```

Create a volume for persistance:

```shell
podman volume create lab4-redis
```

Start the container:

```shell
podman run --name lab4-redis -v lab4-redis:/data -p 127.0.0.1:6379:6379 -d redis redis-server --save 60 1 --loglevel warning
```

The container should now be running:

```shell
podman container ls                                                                                                         
CONTAINER ID  IMAGE                           COMMAND               CREATED        STATUS            PORTS                     NAMES
c1e439839b07  docker.io/library/redis:latest  redis-server --sa...  4 seconds ago  Up 4 seconds ago  127.0.0.1:6379->6379/tcp  lab4-redis
```

The log for my experiment was obtained by running `podman logs lab4-redis` and yielded the following output:

```text
1:C 30 Nov 2022 06:30:20.319 # oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
1:C 30 Nov 2022 06:30:20.319 # Redis version=7.0.5, bits=64, commit=00000000, modified=0, pid=1, just started
1:C 30 Nov 2022 06:30:20.319 # Configuration loaded
1:M 30 Nov 2022 06:30:20.320 # Server initialized
1:M 30 Nov 2022 06:30:20.320 # WARNING overcommit_memory is set to 0! Background save may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
```

For python, install the client:

```shell
pip3 install redis
```

Perform a basic test as per the [GitHub Example](https://github.com/redis/redis-py#basic-example):

```python
>>> import redis
>>> r = redis.Redis(host='localhost', port=6379, db=0)
>>> r.set('foo', 'bar')
True
>>> r.get('foo')
b'bar'
```


