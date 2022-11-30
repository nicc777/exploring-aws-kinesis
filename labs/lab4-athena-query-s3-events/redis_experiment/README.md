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
