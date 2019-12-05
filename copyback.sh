#!/bin/sh

# copy output of process.sh back to original file location
# requires sudo

# choose network - r (real-time) and offline
r_network=Network_42R-004
o_network=Network_42O-004

# choose scenario
#scenario=1
#scenario=2
#scenario=3
scenario=4

# directories
eval_dir='/home/holz501/gocomp/Evaluation/'
data_dir='/home/smb_share/GOComp/'
work_dir=$eval_dir'work/'
case_dir=$data_dir'Challenge_1_Final_Real-Time/'$r_network'/scenario_'$scenario'/'
o_case_dir=$data_dir'Challenge_1_Final_Offline/'$o_network'/scenario_'$scenario'/'

echo "COPY BACK TO ORIGINAL LOCATION" >> $work_dir'process.out'
sudo cp $work_dir'case.raw' $case_dir'case_pre_scrub.raw'
sudo cp $work_dir'case.rop' $case_dir'case_pre_scrub.rop'
sudo cp $work_dir'case.con' $case_dir'case_pre_scrub.con'
sudo cp $work_dir'case.inl' $case_dir'case_pre_scrub.inl'
sudo cp $work_dir'case_clean.raw' $case_dir'case.raw'
sudo cp $work_dir'case_clean.rop' $case_dir'case.rop'
sudo cp $work_dir'case_clean.con' $case_dir'case.con'
sudo cp $work_dir'case_clean.inl' $case_dir'case.inl'
sudo cp $work_dir'worst_case_sol1.txt' $case_dir'worst_case_sol1.txt'
sudo cp $work_dir'worst_case_sol2.txt' $case_dir'worst_case_sol2.txt'
#sudo cp $work_dir'worst_case_summary.csv' $case_dir'worst_case_summary.csv'
sudo cp $work_dir'worst_case_detail.csv' $case_dir'worst_case_detail.csv'
sudo cp $work_dir'process.out' $case_dir'process.out'
sudo cp $work_dir'case_offline.raw' $o_case_dir'case.raw'
sudo cp $work_dir'case_offline.rop' $o_case_dir'case.rop'
sudo cp $work_dir'case_offline.con' $o_case_dir'case.con'
sudo cp $work_dir'case_offline.inl' $o_case_dir'case.inl'

