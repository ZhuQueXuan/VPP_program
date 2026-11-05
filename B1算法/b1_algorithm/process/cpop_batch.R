args<-commandArgs(trailingOnly=TRUE)
if(length(args)!=3)stop('input.csv output.csv R_library required')
if(nzchar(args[3])).libPaths(c(args[3],.libPaths()))
suppressPackageStartupMessages(library(cpop))
input<-read.csv(args[1],stringsAsFactors=FALSE)
groups<-split(input,input$case_id)
result<-vector('list',length(groups));j<-0
for(dat in groups){
 j<-j+1
 tr<-dat[dat$train==1,]
 tic<-proc.time()[['elapsed']]
 result[[j]]<-tryCatch({
  object<-cpop(tr$y,x=tr$x,grid=tr$x,beta=2*log(nrow(tr)),sd=tr$sigma[1],minseglen=0,prune.approx=FALSE)
  seg<-fitted(object);seg$case_id<-dat$case_id[1];seg$native_cost<-cost(object)
  seg$seconds<-proc.time()[['elapsed']]-tic;seg$status<-'ok';seg$error<-'';seg
 },error=function(ex){data.frame(x0=NA,y0=NA,x1=NA,y1=NA,gradient=NA,intercept=NA,RSS=NA,
  case_id=dat$case_id[1],native_cost=NA,seconds=proc.time()[['elapsed']]-tic,status='error',error=conditionMessage(ex))})
}
write.csv(do.call(rbind,result),args[2],row.names=FALSE)
writeLines(capture.output(sessionInfo()),paste0(args[2],'.session.txt'))
