args <- commandArgs(trailingOnly=TRUE)
if(length(args)!=3) stop('usage: cpop_default_batch.R input.csv output.csv R_library')
.libPaths(c(args[3], .libPaths()))
suppressPackageStartupMessages(library(cpop))
input <- read.csv(args[1], stringsAsFactors=FALSE)
ids <- unique(input$event_id)
results <- vector('list',length(ids))
total_start <- proc.time()[['elapsed']]
for(j in seq_along(ids)) {
  dat <- input[input$event_id==ids[j],]
  tic <- proc.time()[['elapsed']]
  fit <- cpop(dat$y,x=dat$x,grid=dat$x,beta=2*log(nrow(dat)),sd=dat$sigma[1],minseglen=0,prune.approx=FALSE)
  segments <- fitted(fit)
  segments$native_seconds <- proc.time()[['elapsed']]-tic
  segments$event_id <- ids[j]
  segments$native_cost <- cost(fit)
  results[[j]] <- segments
  if(j %% 50 == 0) cat('completed',j,'of',length(ids),'elapsed',proc.time()[['elapsed']]-total_start,'s\n')
}
write.csv(do.call(rbind,results),args[2],row.names=FALSE)
writeLines(capture.output(sessionInfo()),paste0(args[2],'.session.txt'))
cat('TOTAL_SECONDS',proc.time()[['elapsed']]-total_start,'\n')
