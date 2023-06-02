# README

[Original project](https://www.decalage.info/python/blindftp)

## usage
### Pitcher
```
arp -s 10.10.10.2 xx:xx:xx:yy:yy:yy
python bftp.py -s sender -a 10.10.10.2 -b
```

### Catcher
```
python bftp.py -r receiver -b
```

-b : Looping files
-a : Destination ip address
-r : Receive files in the specified directory
-s : Synchronize Tree
-p : Port UDP
