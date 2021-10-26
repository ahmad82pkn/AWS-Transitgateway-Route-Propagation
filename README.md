# AWS-Transitgateway-Route-Propagation
This Lambda will Pull propagated routes from TGW and update VPC route table


 #### INSTRUCTIONS#########
    
    #### 1- DONOT USE THIS CODE IF YOU USE PREFIX LISTS ####
    #### 2- Make sure your Lambda Role has permissions to describe/create routes in TGW/VPC and able to create/read from S3 bucket.
    #### 3- This code will only update VPC that belong to same account as of TGW. No cross account support. But feel free to modify the code as per your req.
    #### 4- Populate Variables In below section according to your resource ID's
    #### 5- Customer can use it as cloudwatch cronjob or manually run it when they need to synch up TGW and VPC route tables


    ##########################################VARIABLE SECTION, PLEASE POPULATE AS PER YOUR RESOURCE ID'S################



    #Update TGW ID/TGW REGION/BUCKETNAME  ( If bucket doesnt exist, code will create one )

    tgwid='tgw-0532154ce5738cxxxxx'
    tgwregion='eu-xxx-1'
    bucketname=tgwid+'route-prop'


    # Populate this list with comma separated VPC ID for which you dont want Route propagator to take any action
    # A good canidate would be inepection VPC as it has different VPC route table needs
    VPCExceptionList=['vpc-1234'] # Dont remove this dummy VPC ID 
