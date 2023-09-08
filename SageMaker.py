import json
import sagemaker
import boto3
from sagemaker.huggingface import HuggingFaceModel, get_huggingface_llm_image_uri

try:
	role = sagemaker.get_execution_role()
except ValueError:
	iam = boto3.client('iam')
	role = iam.get_role(RoleName='sagemaker_execution_role')['Role']['Arn']

# Hub Model configuration. https://huggingface.co/models
hub = {
	'HF_MODEL_ID':'WizardLM/WizardCoder-Python-34B-V1.0',
	'SM_NUM_GPUS': json.dumps(1)
}



# create Hugging Face Model Class
huggingface_model = HuggingFaceModel(
	image_uri=get_huggingface_llm_image_uri("huggingface",version="0.9.3"),
	env=hub,
	role=role, 
)

# deploy model to SageMaker Inference
predictor = huggingface_model.deploy(
	initial_instance_count=1,
	instance_type="ml.g5.2xlarge",
	container_startup_health_check_timeout=300,
  )
  
# send request
predictor.predict({
	"inputs": "My name is Julien and I like to",
})