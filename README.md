# SmokedWeaselCheese
Log parser as generator to Pandas Dataframe
Visualise license checkouts, counts, denials etc. from several propriatory license system debug logs

Read the log file in Pass  to Parse, spit out a generator
Read generator lines into dataframe, find checkin events for each checkout, analyse, visualise

* stardrop-vis.py for Log in the form of: 

  > LOG:8charhashUsername#Action_Type#number#Date Time
  >
  > LOG:GQAAJwAKSpot#License_granted#32#19 Nov 2018 06:46  
  > LOG:GQAAJwAKSpot#License_released#32#19 Nov 2018 07:15  
  > LOG:VS9y/9PIErmintrude#License_granted#32#19 Nov 2018 10:29  
  > LOG:VS9y/9PIErmintrude#License_released#32#19 Nov 2018 10:37  

* geneious-vis.py for Log in the form of:

  > 16:01:34 (lmgrd) TIMESTAMP 4/8/2019  
  > 16:06:37 (app-name) TIMESTAMP 4/8/2019  
  > 16:07:10 (app-name) OUT: "floating_license" fbloggs@gbpcx5cg90224lt  
  > 17:05:01 (app name) IN: "floating_license" fbloggs@gbpcx5cg90224lt  
  > 17:16:17 (app-name) OUT: "floating_license" jquser@gbpcx5cg8173xbr  
  > 17:34:06 (app-name) OUT: "floating_license" jblow@gbpcx5cg64931v9  
  > 17:49:19 (app-name) IN: "floating_license" jblow@gbpcx5cg64931v9  
  > 17:53:25 (app-name) IN: "floating_license" jquser@gbpcx5cg8173xbr  (INACTIVE)  

> `usage: Prepares license log for datamining. [-h] [-i HINT] [-s START] [-e END] [-d DUR] filename`  

> positional arguments:  
> filename              path/filename of logfile to file to parse  

> optional arguments:  
>  -h, --help            show this help message and exit  
>  -i HINT, --hint HINT  Hint start date of the log YYYY-MM-DD  
>  -s START, --start START  
>                        Start date YYYY-MM-DDTHH:MM e.g 2020-03-23T13:24  
>  -e END, --end END     End date YYYY-MM-DDTHH:MM  
>  -d DUR, --dur DUR     Duration: Hours, Days, Weeks, e.g. 2W for 2 weeks  

