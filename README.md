# Tools

## To start running pkg :

The package runs initially on ros2 jazzy , success for other distributions not guaranteed

```zsh
cd ~/$YOUR_ROS2_WORKSPACE$/src
git clone -b master https://github.com/Amrskk/turtlesim-llm-agent-killer-and-artist.git
cd ~/$YOUR_ROS2_WORKSPACE$
micromamba activate $YOUR_VIRTUAL_ENV$ && colcon build --packages-select turtlesimLLM --symlink-install
source /opt/ros/jazzy/setup.zsh
source ~/$YOUR_ROS2_WORKSPACE$/install/setup.zsh
#1st terminal
ros2 run turtlesim turtlesim_node
#2nd terminal
ros2 run turtlesimLLM turtle_agent

#3rd terminal for modes

```

## For drawing :

```zsh
ros2 topic pub --once /turtle1/llm_request std_msgs/msg/String "{data: 'draw a circle'}"
ros2 topic pub --once /turtle1/llm_request std_msgs/msg/String "{data: 'please draw a square'}"
ros2 topic pub --once /turtle1/llm_request std_msgs/msg/String "{data: 'make a triangle'}"
ros2 topic pub --once /turtle1/llm_request std_msgs/msg/String "{data: 'stop drawing now'}"
```

## For killing :

killing on auto : stop ollama from systemctl

```zsh
sudo systemctl stop ollama
```

for random enemy pose generator :

```zsh
for i in $(seq 1 5); do
  x=$(awk -v min=1 -v max=10 'BEGIN{srand(); print min+rand()*(max-min)}')
  y=$(awk -v min=1 -v max=10 'BEGIN{srand(); print min+rand()*(max-min)}')
  ros2 service call /spawn turtlesim/srv/Spawn "{x: $x, y: $y, theta: 0.0, name: 'enemy$i'}"
done
```
