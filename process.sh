#!/bin/sh

# copoy to a work directory
# scrub
# check
# create worst case solution
# evaluate worst case solution
# create offline data
#
# then use copyback.sh (requires sudo) to copy files back to original locations

# choose network
# 40 = approach 3 - reduced network
# 41 = approach 2 - full network, convert external generators to loads
# 42 = approach 1 - full network, synthetic realistic cost functions as needed
network=40

# choose scenario
# 1, 2, 3, 4
scenario=4

# choose network - r (real-time) and offline
r_network='Network_'$network'R-004'
o_network='Network_'$network'O-004'

# directories
eval_dir='/home/holz501/gocomp/Evaluation/'
data_dir='/home/smb_share/GOComp/'
work_dir=$eval_dir'work/'
case_dir=$data_dir'Challenge_1_Final_Real-Time/'$r_network'/scenario_'$scenario'/'
o_case_dir=$data_dir'Challenge_1_Final_Offline/'$o_network'/scenario_'$scenario'/'

export PYTHONPATH=$eval_dir:$PYTHONPATH

echo "PROCESSING" > $work_dir'process.out'

if [ -f $case_dir'case_pre_scrub.raw' ]; then

    echo "ORIGINAL DATA:" >> $work_dir'process.out'
    echo $case_dir'case_pre_scrub.raw' >> $work_dir'process.out'
    echo $case_dir'case_pre_scrub.rop' >> $work_dir'process.out'
    echo $case_dir'case_pre_scrub.con' >> $work_dir'process.out'
    echo $case_dir'case_pre_scrub.inl' >> $work_dir'process.out'
    
    echo "COPY ORIGINAL DATA TO WORK DIR" >> $work_dir'process.out'
    cp $case_dir'case_pre_scrub.raw' $work_dir'case.raw'
    cp $case_dir'case_pre_scrub.rop' $work_dir'case.rop'
    cp $case_dir'case_pre_scrub.con' $work_dir'case.con'
    cp $case_dir'case_pre_scrub.inl' $work_dir'case.inl'

else
    
    echo "ORIGINAL DATA:" >> $work_dir'process.out'
    echo $case_dir'case.raw' >> $work_dir'process.out'
    echo $case_dir'case.rop' >> $work_dir'process.out'
    echo $case_dir'case.con' >> $work_dir'process.out'
    echo $case_dir'case.inl' >> $work_dir'process.out'
    
    echo "COPY ORIGINAL DATA TO WORK DIR" >> $work_dir'process.out'
    cp $case_dir'case.raw' $work_dir'case.raw'
    cp $case_dir'case.rop' $work_dir'case.rop'
    cp $case_dir'case.con' $work_dir'case.con'
    cp $case_dir'case.inl' $work_dir'case.inl'

fi

echo "CHECK PRE-SCRUBBED DATA" >> $work_dir'process.out'
python check_data.py $work_dir'case.raw' $work_dir'case.rop' $work_dir'case.con' $work_dir'case.inl' >> $work_dir'process.out'
    
echo "SCRUB DATA" >> $work_dir'process.out'
python scrub_data.py $work_dir'case.raw' $work_dir'case.rop' $work_dir'case.con' $work_dir'case.inl' $work_dir'case_clean.raw' $work_dir'case_clean.rop' $work_dir'case_clean.con' $work_dir'case_clean.inl' >> $work_dir'process.out'

echo "CHECK SCRUBBED DATA" >> $work_dir'process.out'
python check_data.py $work_dir'case_clean.raw' $work_dir'case_clean.rop' $work_dir'case_clean.con' $work_dir'case_clean.inl' >> $work_dir'process.out'

echo "GENERATE WORST CASE SOLUTION" >> $work_dir'process.out'
cd '../WorstCase'
tlim1=600
tlim2=2700
smeth=0
nmod='case2'
python MyPython1.py $work_dir'case_clean.con' $work_dir'case_clean.inl' $work_dir'case_clean.raw' $work_dir'case_clean.rop' $tlim1 $smeth $nmod >> $work_dir'process.out'
cp "solution1.txt" $work_dir"worst_case_sol1.txt"
python MyPython2.py $work_dir'case_clean.con' $work_dir'case_clean.inl' $work_dir'case_clean.raw' $work_dir'case_clean.rop' $tlim2 $smeth $nmod >> $work_dir'process.out'
cp "solution2.txt" $work_dir"worst_case_sol2.txt"
rm "solution1.txt"
rm "solution2.txt"
cd $eval_dir

echo "EVALUATE WORST CASE SOLUTION" >> $work_dir'process.out'
python test.py $work_dir'case_clean.raw' $work_dir'case_clean.rop' $work_dir'case_clean.con' $work_dir'case_clean.inl' $work_dir'worst_case_sol1.txt' $work_dir'worst_case_sol2.txt' $work_dir'worst_case_summary.csv' $work_dir'worst_case_detail.csv' >> $work_dir'process.out'

echo "CREATE OFFLINE VERSION" >> $work_dir'process.out'
python write_offline.py $work_dir'case_clean.raw' $work_dir'case_clean.rop' $work_dir'case_clean.con' $work_dir'case_clean.inl' $work_dir'case_offline.raw' $work_dir'case_offline.rop' $work_dir'case_offline.con' $work_dir'case_offline.inl' >> $work_dir'process.out'

echo "COPY BACK TO ORIGINAL LOCATION" >> $work_dir'process.out'
echo "SKIPPING COPY BACK TO ORIGINAL LOCATION - USE copyback.sh" >> $work_dir'process.out'
#sudo cp $work_dir'case.raw' $case_dir'case_pre_scrub.raw'
#sudo cp $work_dir'case.rop' $case_dir'case_pre_scrub.rop'
#sudo cp $work_dir'case.con' $case_dir'case_pre_scrub.con'
#sudo cp $work_dir'case.inl' $case_dir'case_pre_scrub.inl'
#sudo cp $work_dir'case_clean.raw' $case_dir'case.raw'
#sudo cp $work_dir'case_clean.rop' $case_dir'case.rop'
#sudo cp $work_dir'case_clean.con' $case_dir'case.con'
#sudo cp $work_dir'case_clean.inl' $case_dir'case.inl'
#sudo cp $work_dir'worst_case_sol1.txt' $case_dir'worst_case_sol1.txt'
#sudo cp $work_dir'worst_case_sol2.txt' $case_dir'worst_case_sol2.txt'
##sudo cp $work_dir'worst_case_summary.csv' $case_dir'worst_case_summary.csv'
#sudo cp $work_dir'worst_case_detail.csv' $case_dir'worst_case_detail.csv'
#sudo cp $work_dir'process.out' $case_dir'process.out'
#sudo cp $work_dir'case_offline.raw' $o_case_dir'case.raw'
#sudo cp $work_dir'case_offline.rop' $o_case_dir'case.rop'
#sudo cp $work_dir'case_offline.con' $o_case_dir'case.con'
#sudo cp $work_dir'case_offline.inl' $o_case_dir'case.inl'

echo "DONE" >> $work_dir'process.out'
