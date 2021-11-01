import json
import boto3
import sys

def lambda_handler(event, context):
    
    


    #### INSTRUCTIONS#########
    
    #### 1- DONOT USE THIS CODE IF YOU USE PREFIX LISTS ####
    #### 2- Make sure your Lambda Role has permissions to describe/create routes in TGW/VPC and able to create/read from S3 bucket.
    #### 3- This code will only update VPC that belong to same account as of TGW. No cross account support. But feel free to modify the code as per your req.
    #### 4- Populate Variables In below section according to your resource ID's



    ##########################################VARIABLE SECTION, PLEASE POPULATE AS PER YOUR RESOURCE ID'S################



    #Update TGW ID/TGW REGION
    tgwid='tgw-0xxxxxxxx'
    tgwregion='xx-xxxx-1'



    # Populate this list with comma separated VPC ID for which you dont want Route propagator to take any action
    # A good canidate would be inepection VPC as it has different VPC route table needs
    VPCExceptionList=['vpc-1234'] # Dont remove this dummy VPC ID 


    ##########################################CODE START HERE##############################################################
    #Check if VPC route table are reaching route table entries per vpc
    def check_vpc_route_table_enteries_quota(tgw_new_route_count,rtblist):
        ec2client = boto3.client('service-quotas',region_name=tgwregion)

        response = ec2client.list_service_quotas(
        ServiceCode='vpc'
        )
        for i in response['Quotas']:
            if i['QuotaName']=="Routes per route table":
                vpc_rtb_quota=i['Value']

        
        largest_route_table_count=0
        tgwclient = boto3.client('ec2',region_name=tgwregion)
        for rtb in rtblist:
            response = tgwclient.describe_route_tables(
                RouteTableIds=[
                 rtb,
             ],
                )

            current_rtb_route_count=0

            for i in response['RouteTables'][0]['Routes']:
                if i['Origin']=='CreateRoute':
                    current_rtb_route_count=current_rtb_route_count+1
            if current_rtb_route_count>largest_route_table_count:
                largest_route_table_count=current_rtb_route_count
                rtb_with_quota_issue=rtb
        
        available_capacity=vpc_rtb_quota-largest_route_table_count

        if available_capacity<tgw_new_route_count:
            print("Number of available route entries quota in VPC RTB " + rtb_with_quota_issue + "is less than additional new TGW routes. Cant create route in VPC RTB rtb_with_quota_issue, please increase capacity ! Aborting")
            exit()
        
        


    #Get list of routes from S3
    def get_list_of_routes_from_s3():

        tgwroutes_in_s3=[]    
        s3 = boto3.resource(service_name = 's3', region_name=tgwregion)
        try:

            s3.meta.client.download_file(Bucket=tgwid+'-route-prop',Key='file.txt',Filename ='/tmp/file.txt')
            with open("/tmp/file.txt","r") as readnow:
                for line in readnow:
                    tgwroutes_in_s3.append(line.rstrip())
            return tgwroutes_in_s3
        except Exception as e:

            error_code = int(e.response['Error']['Code'])
            if error_code == 404:

                print("Creatingbucket")
                if tgwregion=='us-east-1':
                    s3.create_bucket(Bucket=tgwid+'-route-prop')
                else:
                    s3.create_bucket(Bucket=tgwid+'-route-prop', CreateBucketConfiguration={'LocationConstraint': tgwregion})
                bucket_versioning = s3.BucketVersioning(tgwid+'-route-prop')
                bucket_versioning.enable()
            else:
                print("S3 Timedout. Aborting")
                exit()
            return tgwroutes_in_s3

    #Update TGW routes in S3        
    def update_list_of_routes_in_s3(mylist):
        s3 = boto3.resource(service_name = 's3', region_name=tgwregion)
        with open("/tmp/file.txt", "w") as output:
            for x in mylist:
                output.write(x+"\n")

        s3.meta.client.upload_file(Filename ='/tmp/file.txt',Bucket=tgwid+'-route-prop',Key='file.txt')

    # Find VPC RTB that has a route conflicting with TGW RTB( already present in TGW ) You need to remove conflicting route from VPC RTB pointing to next hop other than TGW, so that script can push TGW route to VPC RTB pointing to TGW as next hop
    def find_rtb_of_conflicting_route(route,rtblist):

        for eachrtb in rtblist:
            response = tgwclient.describe_route_tables(
            RouteTableIds=[
             eachrtb,
            ],
            )
            for ii in response['RouteTables'][0]['Routes']:
                if ii['DestinationCidrBlock'] in route:
                    print("Conflicting route "+ ii['DestinationCidrBlock'] + " in route table " + eachrtb + " Program Exiting" ) 



    #   Take VPC RTB list as argument and return any static route in VPC pointing to IGW/ENI/VPCEndpoint/Instance/VGW that conflict with route in TGW and signal a conflict to exit the code (It will ignore VPC Local Route and static route pointing to TGW )
    def list_of_nonlocal_static_routes_in_vpc_rtb(rtblist):

        listofVPClocalroutes=[]
        listofALLroutesinvpcrtb=[]
        listofNONlocalstaticroute=[]
        listofVPCRoutePointingToTGW=[]
        tgwclient = boto3.client('ec2',region_name=tgwregion)
        for eachrtb in rtblist:
            response = tgwclient.describe_route_tables(
            RouteTableIds=[
             eachrtb,
            ],
            )
            for ii in response['RouteTables'][0]['Routes']:
                if ii['DestinationCidrBlock'] not in listofALLroutesinvpcrtb:
                    listofALLroutesinvpcrtb.append(ii['DestinationCidrBlock'])
                if 'GatewayId' in ii and ii['GatewayId']=='local':
                    if ii['DestinationCidrBlock'] not in listofVPClocalroutes:
                        listofVPClocalroutes.append(ii['DestinationCidrBlock'])
                if 'TransitGatewayId' in ii and ii['TransitGatewayId']==tgwid:
                    if ii['DestinationCidrBlock'] not in listofVPCRoutePointingToTGW:
                        listofVPCRoutePointingToTGW.append(ii['DestinationCidrBlock'])
        print("VPC ALL ROUTES ",listofALLroutesinvpcrtb)
        for route in listofALLroutesinvpcrtb:
            if route not in listofVPClocalroutes and (route not in ListOfAllTgwRoutes):
    #Check to avoid duplicate entries
                if (route not in listofNONlocalstaticroute):
                    listofNONlocalstaticroute.append(route)
            elif route not in listofVPClocalroutes and (route not in listofVPCRoutePointingToTGW):
    #Check to avoid duplicate entries
                if (route not in listofNONlocalstaticroute):
                    listofNONlocalstaticroute.append(route)
        
       
        return listofNONlocalstaticroute



    ListOfRtb=[]
    ListOfAllTgwRoutes=[]



    tgwclient = boto3.client('ec2',region_name=tgwregion)

    response = tgwclient.describe_transit_gateways(
    TransitGatewayIds=[
        tgwid,
    ]
    )
    tgwownerid=response['TransitGateways'][0]['OwnerId']



    # Describe a TGW Route table by TGW ID
    response = tgwclient.describe_transit_gateway_route_tables(
        Filters=[
            {
                'Name': 'transit-gateway-id',
                'Values': [
                    tgwid,
                ]
            },
        ],
    )


    # Create List of TGW Route Table ListOfRtb 

    for i in response['TransitGatewayRouteTables']:
        if i['State']=='available':
            ListOfRtb.append(i['TransitGatewayRouteTableId'])


    # In each  TGW RTB  search for Propagated Routes(VPC+ BGP VPN+ BGP DX) and create a list of those routes 
    # List name ListOfAllTgwRoutes

    for rtb1 in ListOfRtb:
        response1 = tgwclient.search_transit_gateway_routes(
             TransitGatewayRouteTableId=rtb1,
            Filters=[
                {
                    'Name': 'type',
                    'Values': [
                        'propagated',
                    ]
                },
            ],


        )

        for i in response1['Routes']:
            if i['DestinationCidrBlock'] not in ListOfAllTgwRoutes:
                ListOfAllTgwRoutes.append(i['DestinationCidrBlock'])
                
                

    print("TGW ROUTES ",ListOfAllTgwRoutes)
    tgw_route_count=len(ListOfAllTgwRoutes)



    # Create List of VPC from same account Attached with TGW ( No cross account VPC attachment support )
    # Create List of Route Tables in those VPC 

    getvpcid = tgwclient.describe_transit_gateway_attachments(
        Filters=[
            {
                'Name': 'resource-type',
                'Values': [
                    'vpc',
                ]
            },
            {
                'Name': 'transit-gateway-id',
                'Values': [
                    tgwid,
                ]
            },
            {
                'Name': 'transit-gateway-owner-id',
                'Values': [
                    tgwownerid,
                ]
            }
        ],

    )

    ListOfVpc=[]
    ListOfVpcRtb=[]



    for eachvpcid in getvpcid['TransitGatewayAttachments']:
        vpcid=eachvpcid['ResourceId']
        if vpcid not in VPCExceptionList:
            ListOfVpc.append(vpcid)




    # Create a List of RTB of All VPC
    for vpc in ListOfVpc:
        describertb = tgwclient.describe_route_tables(
            Filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [
                        vpc,
                    ]
                },
            ],

    )

        for rtb in describertb['RouteTables']:
            ListOfVpcRtb.append(rtb['RouteTableId'])



    #List of static route in VPC RTB pointing to ENI/VGW/IGW etc 
    staticrouteinvpc=list_of_nonlocal_static_routes_in_vpc_rtb(ListOfVpcRtb)        

    # Emptry Lists
    tgw_routes_from_s3=[]
    tgw_routes_from_s3_copy=[]
    update=False



    # Grab TGW routes from last saved copy in S3
    tgw_routes_from_s3=get_list_of_routes_from_s3()
    tgw_route_count_from_s3=len(tgw_routes_from_s3)
    # Create copy of TGW routes pulled from S3
    tgw_routes_from_s3_copy=tgw_routes_from_s3[:]

    new_tgw_route_to_add_in_vpc=tgw_route_count-tgw_route_count_from_s3
    
    #Check if VPC route table are reaching route table entries per vpc
    check_vpc_route_table_enteries_quota(new_tgw_route_to_add_in_vpc,ListOfVpcRtb)
    
    
    # This function will check if TGW routes conflict with any existing static VPC route. If a conflict found Code will exit

    conflict_list = [element for element in staticrouteinvpc if element in ListOfAllTgwRoutes]


    if conflict_list:
        print("Conflicting route present  in VPCRTB  and TGWRTB. Please delete this route from VPC RTB and run the code again ",conflict_list)
        find_rtb_of_conflicting_route(conflict_list,ListOfVpcRtb)
        exit()

    # Update any new  TGW routes in VPC Route table + Update s3 list with additional routes and upload to S3

    print("For CreateRoute VPC API, getting copy of TGW routes from S3",tgw_routes_from_s3)
    #print("List of routes present in TGW Route table ",ListOfAllTgwRoutes)
    for rtb in ListOfVpcRtb:
        for route in ListOfAllTgwRoutes:
            if route not in tgw_routes_from_s3:
                try:
                    response = tgwclient.create_route(
                    DestinationCidrBlock=route,
                    GatewayId=tgwid,
                    RouteTableId=rtb
                    )
                    print("Adding TGW Route "+route+" in VPC route table "+rtb)
#                    print(response)
                    if route not in tgw_routes_from_s3_copy:
                        tgw_routes_from_s3_copy.append(route)
                    update=True

                except:
                    pass
    #                print("Already Existing Route",route,"+",rtb)



    if update:

        print("Updating S3 with TGW Routes",tgw_routes_from_s3_copy)
        update_list_of_routes_in_s3(tgw_routes_from_s3_copy)
    else:

        print("TGW and VPC are Synched , No routes added in VPC RTB")    

    # Delete Additional Routes from VPC RTB that are not present or active in TGW RTB.

    update=False

    tgw_routes_from_s3=[]
    tgw_routes_from_s3_copy=[]
    tgw_routes_from_s3=get_list_of_routes_from_s3()
    tgw_routes_from_s3_copy=tgw_routes_from_s3[:]

    print("For DeleteRoute VPC API , getting last copy of TGW routes stored in S3",tgw_routes_from_s3)

    print("Here is copy of tgw_routes_from_s3_copy",tgw_routes_from_s3_copy)

    print("List of routes currently present in TGW Route table ",ListOfAllTgwRoutes)

    for rtb in ListOfVpcRtb:

        for route in tgw_routes_from_s3:
            if route not in ListOfAllTgwRoutes:
                try:
                    
                    response = tgwclient.delete_route(
                    DestinationCidrBlock=route,
                    RouteTableId=rtb
                    )
                    print("Deleting Route %s from VPC route table %s as its not present in TGW route table anymore" %(route,rtb))

                    tgw_routes_from_s3_copy.remove(route)
                    print("Remaing list",tgw_routes_from_s3_copy)

                    update=True
                except:
                    pass
    if update:
        print("Update S3 with List1",tgw_routes_from_s3_copy)
        update_list_of_routes_in_s3(tgw_routes_from_s3_copy)

    else:
        print("TGW and VPC are Synched , No routes deleted from VPC RTB")





    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
