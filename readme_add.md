# 安装步骤
1. sudo docker pull dockerymh/unigbsa:0.1.0
1. 查看镜像：sudo docker image list
1. 查看容器：sudo docker ps -a
# 选择工作目录
1. sudo wget https://codeload.github.com/dptech-corp/Uni-GBSA/zip/refs/heads/master
2. 解压：unzip master
# 创建容器
docker_run.sh(docker run --privileged -it -v /home/zhangqihua/docker_gbsa/Uni-GBSA-master:/workspace  --name gbsa  dockerymh/unigbsa:0.1.0   /bin/bash)
# 退出
exit
# 启动 
docker start 05938cc8f193
# 进入容器
sudo docker exec -it 05938cc8f193  /bin/bash
