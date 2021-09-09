# Semantic-model
All data about data in one model.
The single source of truth about data in one model.


### Create initial sm model
'''sh
python3 -m semantic_model -mode one_to_one -input example.json > sm_model.json

'''

### Run sm model
'''sh
python3 -m semantic_model -input example.json -sm sm_model.json
'''

### Display sm model
'''sh
sudo docker run -i attumm/dsm_png:latest < sm_model.json > output.png
'''
