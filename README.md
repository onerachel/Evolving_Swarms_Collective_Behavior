# Environment induced emergence of collective behavior in evolving swarms with limited sensing

[Paper](https://dl.acm.org/doi/abs/10.1145/3512290.3528735)

## Installation
REQUIREMENTS

This pipeline requires the following for the simulator [Isaac Gym](https://developer.nvidia.com/isaac-gym):
* Ubuntu 18.04 or 20.04
* CUDAnn
* Python 3.6, 3.7, 3.8

STEPS
1. clone the repository
```bash
git clone git@github.com:onerachel/Evolvable_Morphology_Learning_Controller.git
```

2. Download and extract Isaac Gym in the `/thirdparty/` folder (can be downloaded from [here](https://developer.nvidia.com/isaac-gym))
3. Create a Python virtual environment in the `EC_swarm' root directory:
```bash
virtualenv -p=python3.8 .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Partial results

<img width="617" alt="Screenshot 2022-12-26 at 14 20 59" src="https://user-images.githubusercontent.com/75667244/209553330-640a7a41-c4c4-43b0-aeb9-a7c7310ed4a0.png">

<img width="599" alt="Screenshot 2022-12-26 at 14 20 01" src="https://user-images.githubusercontent.com/75667244/209553261-63e77b21-d5b6-480b-b747-ba45100e9088.png">

<img width="603" alt="Screenshot 2022-12-26 at 14 16 40" src="https://user-images.githubusercontent.com/75667244/209553075-94596bcd-30ca-4b6e-bb9d-0d7055c45620.png">
