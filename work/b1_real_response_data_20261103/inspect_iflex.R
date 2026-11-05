# Read the existing official archive; export schema only, not outcome values.
args <- commandArgs(trailingOnly=TRUE)
root <- normalizePath(args[[1]], winslash="/", mustWork=TRUE)
out <- file.path(root,"work/b1_real_response_data_20261103/iflex_schema.tsv")
stopifnot(!file.exists(out))
source <- file.path(root,"data/public_datasets/挪威_iFlex_动态电价试验/iFlex_dataset.RData")
e <- new.env(parent=emptyenv())
n <- load(source,envir=e)
rows <- list()
for (name in n) {
  x <- get(name,envir=e)
  cat("OBJECT",name,"CLASS",paste(class(x),collapse="|"),"SIZE",format(object.size(x)),"DIM",paste(dim(x),collapse="x"),"\n")
  if (is.data.frame(x)) {
    for (field in names(x)) {
      y <- x[[field]]
      rows[[length(rows)+1L]] <- data.frame(object=name,rows=nrow(x),columns=ncol(x),field=field,
        class=paste(class(y),collapse="|"),length=length(y),stringsAsFactors=FALSE)
    }
  } else {
    rows[[length(rows)+1L]] <- data.frame(object=name,rows=ifelse(is.null(dim(x)),length(x),dim(x)[1]),
      columns=ifelse(is.null(dim(x)),NA,dim(x)[2]),field=paste(names(x),collapse="|"),
      class=paste(class(x),collapse="|"),length=length(x),stringsAsFactors=FALSE)
  }
}
write.table(do.call(rbind,rows),out,sep="\t",quote=TRUE,row.names=FALSE,na="")
cat("SCHEMA_WRITTEN",out,"\n")
