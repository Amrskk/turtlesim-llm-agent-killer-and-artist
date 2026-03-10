# Tools

## To start running pkg :

```zsh
micromamba activate ds
ros
cd ~/ros2_ws
sws
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
ollstop
```

for random enemy pose generator :

```zsh
for i in $(seq 1 5); do
  x=$(awk -v min=1 -v max=10 'BEGIN{srand(); print min+rand()*(max-min)}')
  y=$(awk -v min=1 -v max=10 'BEGIN{srand(); print min+rand()*(max-min)}')
  ros2 service call /spawn turtlesim/srv/Spawn "{x: $x, y: $y, theta: 0.0, name: 'enemy$i'}"
done
```
