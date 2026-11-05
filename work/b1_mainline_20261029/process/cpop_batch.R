# Original CRAN cpop, no custom segmentation implementation.
args <- commandArgs(trailingOnly=TRUE)
if(length(args)!=3) stop('usage: cpop_batch.R input.csv output.csv R_library')
.libPaths(c(args[3], .libPaths()))
suppressPackageStartupMessages(library(cpop))
input <- read.csv(args[1], stringsAsFactors=FALSE)
ids <- unique(input$event_id)
results <- vector('list',length(ids))
for(j in seq_along(ids)) {
  dat <- input[input$event_id==ids[j],]
  grid <- sort(unique(c(-15,seq(-8.3,43.7,by=4),45)))
  fit <- cpop(dat$y,x=dat$x,grid=grid,beta=2*log(nrow(dat)),sd=dat$sigma[1],minseglen=0,prune.approx=FALSE)
  segments <- fitted(fit)
  segments$event_id <- ids[j]
  segments$native_cost <- cost(fit)
  results[[j]] <- segments
  if(j %% 100 == 0) cat('completed',j,'of',length(ids),'\n')
}
write.csv(do.call(rbind,results),args[2],row.names=FALSE)
writeLines(capture.output(sessionInfo()),paste0(args[2],'.session.txt'))
