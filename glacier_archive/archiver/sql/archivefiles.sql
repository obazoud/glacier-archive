delimiter %%
use glacier_archive %%
drop table if exists R_ObjectId_seq_tbl %%
create table R_ObjectId_seq_tbl ( nextval bigint not null primary key auto_increment ) engine = MyISAM %%
alter table R_ObjectId_seq_tbl AUTO_INCREMENT = 10000 %%

drop function if exists R_ObjectId_nextval %%
create function R_ObjectId_nextval()
returns bigint
begin
   insert into R_ObjectId_seq_tbl values (NULL) ;
   set @R_ObjectId_val=LAST_INSERT_ID() ;
   delete from R_ObjectId_seq_tbl ;
   return @R_ObjectId_val ;
end
%%

drop function if exists R_ObjectId_currval %%
create function R_ObjectId_currval()
returns bigint
deterministic
begin
    return @R_ObjectId_val ;
end
%%

delimiter ;
