# Prepare real observations using a design frozen without inspecting outcomes.
# Base R only. Original RData and all former artifacts stay unchanged.
args <- commandArgs(trailingOnly=TRUE)
root <- normalizePath(args[[1]],winslash="/",mustWork=TRUE)
out <- file.path(root,"work/b1_real_response_data_20261103")
raw <- file.path(root,"data/public_datasets/挪威_iFlex_动态电价试验")
stopifnot(!file.exists(file.path(out,"prepared_P_events.csv")))
design <- read.csv(file.path(out,"selected_design.csv"),stringsAsFactors=FALSE)
e <- new.env(parent=emptyenv());load(file.path(raw,"iFlex_dataset.RData"),envir=e)
all <- e$data_hourly
cat("FULL_ARCHIVE_ROWS",nrow(all),"\n")
phase_registry <- aggregate(list(rows=seq_len(nrow(all))),list(phase=as.character(all$Participation_Phase)),length)
phase_registry$users <- vapply(phase_registry$phase,function(p) length(unique(all$ID[as.character(all$Participation_Phase)==p])),integer(1))
write.csv(phase_registry,file.path(out,"archive_phase_registry.csv"),row.names=FALSE,fileEncoding="UTF-8")
p <- e$participants
ids <- as.character(p$ID[!is.na(p$Group_Phase2) & as.character(p$Group_Phase2) %in% c("H2","Os_2","Trom_2")])
stopifnot(length(unique(ids))==length(ids))
source_index <- which(as.character(all$Participation_Phase)=="Phase_2" & all$ID %in% ids)
dat <- all[source_index,];dat$.source_row <- source_index
by_id <- split(seq_len(nrow(dat)),dat$ID)
rows <- list();registry <- list()
for (id in ids) {
  meta <- p[as.character(p$ID)==id,]
  group <- as.character(meta$Group_Phase2)
  dd <- design[design$Group==group,]
  ix <- by_id[[id]]
  if (is.null(ix)) ix <- integer(0)
  x <- dat[ix,];x <- x[order(x$From),]
  times <- as.numeric(x$From)
  values <- x$Demand_kWh
  csum <- c(0,cumsum(ifelse(is.finite(values),values,0)))
  ccnt <- c(0,cumsum(is.finite(values)))
  ctemp <- c(0,cumsum(ifelse(is.finite(x$Temperature),x$Temperature,0)))
  cntemp <- c(0,cumsum(is.finite(x$Temperature)))
  prefix <- function(notice,hours) {
    left <- findInterval(notice-hours*3600-0.001,times)
    right <- findInterval(notice-3600,times)
    n <- max(0L,right-left)
    good <- ccnt[right+1L]-ccnt[left+1L]
    st <- if(n>0) times[right]+3600 else NA_real_
    z <- if(good==hours && n==hours) csum[right+1L]-csum[left+1L] else NA_real_
    nt <- cntemp[right+1L]-cntemp[left+1L]
    temp <- if(nt==hours && n==hours) (ctemp[right+1L]-ctemp[left+1L])/hours else NA_real_
    list(rows=n,finite=good,value=z,temp=temp,last_end=st,
         first_source=if(n>0)x$.source_row[left+1L] else NA_integer_,last_source=if(n>0)x$.source_row[right] else NA_integer_)
  }
  registry[[length(registry)+1L]] <- data.frame(ID=id,Group=group,Region=as.character(meta$Region),
    raw_phase2_rows=nrow(x),designed_events=nrow(dd),
    has_phase1=any(as.character(all$Participation_Phase[all$ID==id])=="Phase_1"),stringsAsFactors=FALSE)
  for (j in seq_len(nrow(dd))) {
    z <- dd[j,];date <- as.character(z$Date)
    # Winter dates before March28:18:00 Europe/Oslo is17:00UTC.
    notice <- as.numeric(as.POSIXct(paste(as.Date(date)-1,"17:00:00"),tz="UTC"))
    event <- x[as.character(x$Date)==date,]
    hour <- as.integer(as.character(event$Hour))
    peak <- event[hour %in% c(17L,18L),]
    peak_hour <- as.integer(as.character(peak$Hour))
    day_ok <- nrow(event)==24L && identical(sort(hour),1:24) && length(unique(event$From))==24L && all(is.finite(event$Demand_kWh))
    peak_ok <- nrow(peak)==2L && identical(sort(peak_hour),17:18) && all(is.finite(peak$Demand_kWh))
    signal <- as.character(z$Price_signal)
    prices <- e$price_signals[as.character(e$price_signals$Price_signal)==signal,]
    prices <- prices[order(as.integer(as.character(prices$Hour))),]
    expected <- prices$Experiment_price_NOK_kWh[match(hour,as.integer(as.character(prices$Hour)))]
    signal_ok <- nrow(event)>0 && all(!is.na(event$Price_signal)) && all(as.character(event$Price_signal)==signal)
    price_ok <- nrow(event)>0 && all(is.finite(event$Experiment_price_NOK_kWh)) && all(abs(event$Experiment_price_NOK_kWh-expected)<1e-10)
    pre24 <- prefix(notice,24L);pre168 <- prefix(notice,168L)
    time_ok <- (is.na(pre24$last_end)||pre24$last_end<=notice) && (is.na(pre168$last_end)||pre168$last_end<=notice)
    stopifnot(time_ok)
    rows[[length(rows)+1L]] <- data.frame(ID=id,Group=group,Region=as.character(meta$Region),Date=date,
      split=as.character(z$split),assigned_signal=signal,nominal_price_level=as.numeric(sub("P_","",signal)),
      notice_utc=format(as.POSIXct(notice,origin="1970-01-01",tz="UTC"),"%Y-%m-%dT%H:%M:%SZ",tz="UTC"),
      event_rows=nrow(event),peak_rows=nrow(peak),complete_day=day_ok,complete_peak=peak_ok,
      signal_matches=signal_ok,price_matches=price_ok,
      actual_day_kwh=if(day_ok)sum(event$Demand_kWh) else NA_real_,
      actual_peak_2h_kwh=if(peak_ok)sum(peak$Demand_kWh) else NA_real_,
      negative_event_readings=sum(event$Demand_kWh<0,na.rm=TRUE),
      pre24_rows=pre24$rows,pre24_finite=pre24$finite,pre24_kwh=pre24$value,pre24_temperature=pre24$temp,
      pre168_rows=pre168$rows,pre168_finite=pre168$finite,pre168_kwh=pre168$value,
      pre24_last_end_utc=if(is.na(pre24$last_end))NA_character_ else format(as.POSIXct(pre24$last_end,origin="1970-01-01",tz="UTC"),"%Y-%m-%dT%H:%M:%SZ",tz="UTC"),
      pre168_last_end_utc=if(is.na(pre168$last_end))NA_character_ else format(as.POSIXct(pre168$last_end,origin="1970-01-01",tz="UTC"),"%Y-%m-%dT%H:%M:%SZ",tz="UTC"),
      pre24_source_first=pre24$first_source,pre24_source_last=pre24$last_source,
      pre168_source_first=pre168$first_source,pre168_source_last=pre168$last_source,
      event_source_rows=paste(event$.source_row,collapse=";"),peak_source_rows=paste(peak$.source_row,collapse=";"),
      stringsAsFactors=FALSE)
  }
}
events <- do.call(rbind,rows)
write.csv(events,file.path(out,"prepared_P_events.csv"),row.names=FALSE,na="",fileEncoding="UTF-8")
write.csv(do.call(rbind,registry),file.path(out,"P_household_registry.csv"),row.names=FALSE,fileEncoding="UTF-8")
summary <- aggregate(list(designed_events=seq_len(nrow(events)),complete_day=as.integer(events$complete_day),
  complete_peak=as.integer(events$complete_peak),matched_signal=as.integer(events$signal_matches),
  matched_price=as.integer(events$price_matches),pre24_ready=as.integer(is.finite(events$pre24_kwh)),
  pre168_ready=as.integer(is.finite(events$pre168_kwh))),list(split=events$split),sum)
# Replace sum of row indices with actual event counts.
summary$designed_events <- as.integer(table(factor(events$split,levels=summary$split)))
write.csv(summary,file.path(out,"preparation_counts.csv"),row.names=FALSE,fileEncoding="UTF-8")
cat("PREPARED_HOUSEHOLDS",length(ids),"DESIGNED_HOUSEHOLD_EVENTS",nrow(events),"\n")
print(summary,row.names=FALSE)
