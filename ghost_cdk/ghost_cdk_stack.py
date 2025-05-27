from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

class GhostCdkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Create a VPC
        vpc = ec2.Vpc(self, "GhostVPC", max_azs=2)

        # 2. Security group for EC2
        ec2_sg = ec2.SecurityGroup(self, "EC2SG", vpc=vpc, description="Allow HTTP & SSH")
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH access")
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(2368), "Ghost CMS")

        # 3. Security group for RDS
        rds_sg = ec2.SecurityGroup(self, "RDSSG", vpc=vpc, description="Allow MySQL access from EC2")
        rds_sg.add_ingress_rule(ec2_sg, ec2.Port.tcp(3306), "Allow MySQL from EC2")

        # 4. RDS MySQL instance
        db = rds.DatabaseInstance(
            self, "GhostRDS",
            engine=rds.DatabaseInstanceEngine.mysql(version=rds.MysqlEngineVersion.VER_8_0),
            vpc=vpc,
            credentials=rds.Credentials.from_generated_secret("ghostadmin"),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO),
            multi_az=False,
            allocated_storage=20,
            max_allocated_storage=100,
            security_groups=[rds_sg],
            vpc_subnets={"subnet_type": ec2.SubnetType.PUBLIC},
            removal_policy=RemovalPolicy.DESTROY,
        )

        # 5. EC2 user data to install Docker + Ghost
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "sudo yum update -y",
            "sudo amazon-linux-extras install docker -y",
            "sudo service docker start",
            "sudo usermod -a -G docker ec2-user",
            "docker run -d --name ghost-blog -p 2368:2368 ghost"
        )

        # 6. EC2 instance
        ec2_instance = ec2.Instance(
            self, "GhostEC2",
            instance_type=ec2.InstanceType("t3.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            vpc=vpc,
            security_group=ec2_sg,
            vpc_subnets={"subnet_type": ec2.SubnetType.PUBLIC},
            user_data=user_data
        )

       CfnOutput(self, "GhostCMSPublicIP", value=ec2_instance.instance_public_ip)
