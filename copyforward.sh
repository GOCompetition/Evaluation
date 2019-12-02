#!/bin/sh

# copy raw data from Ahmad to main data dir
# requires sudo

# network - approach:
# N40 = A3
# N41 = A2
# N42 = A1

# scenario - case - time:
# S1 = C1 = T1330
# S2 = C2 = T1345
# S3 = C3 = T1400
# S4 = C4 = T1415

echo "COPY FROM AHMAD"

scenario=1
case=1
time=1330
approach=3
network=40
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'

scenario=1
case=1
time=1330
approach=2
network=41
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'

scenario=1
case=1
time=1330
approach=1
network=42
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'

#scenario=2
#case=2
#time=1345
#approach=3
#network=40
#in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
#out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
#echo "in: $in_name, out: $out_name"
#sudo cp $in_name'.raw' $out_name'.raw'
#sudo cp $in_name'.rop' $out_name'.rop'
#sudo cp $in_name'.inl' $out_name'.inl'
#sudo cp $in_name'.con' $out_name'.con'

scenario=2
case=2
time=1345
approach=2
network=41
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'

scenario=2
case=2
time=1345
approach=1
network=42
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'

##
return

scenario=3
case=3
time=1400
approach=3
network=40
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'

scenario=3
case=3
time=1400
approach=2
network=41
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'

scenario=3
case=3
time=1400
approach=1
network=42
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'

scenario=4
case=4
time=1415
approach=3
network=40
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'

scenario=4
case=4
time=1415
approach=2
network=41
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'

scenario=4
case=4
time=1415
approach=1
network=42
in_name='/home/smb_share/tbai440/holz501/Case'$case'/Approach'$approach'/hour_00_2018_09_28_'$time'_approach'$approach
out_name='/home/smb_share/GOComp/Network_'$network'R-004/scenario_'$scenario'/case_pre_scrub'
echo "in: $in_name, out: $out_name"
sudo cp $in_name'.raw' $out_name'.raw'
sudo cp $in_name'.rop' $out_name'.rop'
sudo cp $in_name'.inl' $out_name'.inl'
sudo cp $in_name'.con' $out_name'.con'
