
# Infra Sample

This folder is an independend Python module which deploys a sample stack with some resources which then can later be visualized with AWS CDK

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .env
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .env/bin/activate
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

## Deployment

As this repo uses AWS CDK the CDK CLI need to be installed first:
```
npm install -g aws-cdk
```

The resources in this template should not really cost a lot of many (basically free). To deploy the stacks included in here execute the following:
```
cdk deploy '*'
```

You can visualize the resources now with:
```
infra-graph export --refresh -t testproject1
```

If you don't need the resources anymore you can delete the stacks with the following command:
```
cdk destroy '*'
```
