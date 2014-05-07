---
layout: post
title: "简析 gcc 中 lambda 表达式的实现"
description: ""
category: C++
tags: [C++, STL, GCC, code reading]
---
{% include JB/setup %}
昨天下午搞了 std::function, 晚上在想要不顺便把 lambda 原理大概看一下好了，顺便了解一下 gcc。于是今天下午就搞起~

prerequisite
1.  [c++ lambda](http://en.cppreference.com/w/cpp/language/lambda)
2.  编译基础知识

代码来源于 gcc trunk，如果图方便可以直接到 [github](https://github.com/mirrors/gcc) 下一个 zip 回来，或者直接在线看。

首先 grep lambda 

发现在这里有粗线。
gcc/cp/parser.c 
line 1965

{% highlight cpp %}
static tree cp_parser_lambda_expression
  (cp_parser *);
static void cp_parser_lambda_introducer
  (cp_parser *, tree);
static bool cp_parser_lambda_declarator_opt
  (cp_parser *, tree);
static void cp_parser_lambda_body
  (cp_parser *, tree);
{% endhighlight %}

<!--more-->
line 3078
{% highlight cpp %}
/* This is good for lambda expression capture-lists. */
     CPP_OPEN_SQUARE:
  ++square_depth;
  break;
     CPP_CLOSE_SQUARE:
  if (!square_depth--)
    return 0;
  break;
{% endhighlight %}

看来这里是在做 \[\] 的事情，也就是 lambda 的 capture list，继续往下看。

line 4316
{% highlight cpp %}
    case CPP_OPEN_SQUARE:
      if (c_dialect_objc ())
        /* We have an Objective-C++ message. */
        return cp_parser_objc_expression (parser);
      {
        tree lam = cp_parser_lambda_expression (parser);
        /* Don't warn about a failed tentative parse. */
        if (cp_parser_error_occurred (parser))
          return error_mark_node;
        maybe_warn_cpp0x (CPP0X_LAMBDA_EXPR);
        return lam;
      }
{% endhighlight %}

这里应该是 parse lambda 的地方。网上看，我们是在 cp\_parser\_primary\_expression 这个函数内
也就是说 lambda 是 primary expression 的一种。

gcc/c-family/c-common.h
line 466

{% highlight cpp %}
#define c_dialect_objc() ((c_language & clk_objc) != 0)
{% endhighlight %}

也就是判断是不是 objective-C。那我们不管他，继续向下看 cpp parse 的部分。

line 8717
{% highlight cpp %}
static tree
cp_parser_lambda_expression (cp_parser* parser)
  tree lambda_expr = build_lambda_expr ();
  tree type;
  bool ok = true;
  cp_token *token = cp_lexer_peek_token (parser->lexer);
  LAMBDA_EXPR_LOCATION (lambda_expr) = token->location;
  if (cp_unevaluated_operand)
    {
      if (!token->error_reported)
        {
          error_at (LAMBDA_EXPR_LOCATION (lambda_expr),
                    "lambda-expression in unevaluated context");
          token->error_reported = true;
        }
      ok = false;
    }
{% endhighlight %}

终于我们找到了他！ 我们一步一步慢慢来看。首先是  build\_lambda\_expr()，
应该是构建 parse tree 中的 lambda 对象。

gcc/cp/lambda.c
line 37
{% highlight cpp %}
tree
build_lambda_expr (void)
{
  tree lambda = make_node (LAMBDA_EXPR);
  LAMBDA_EXPR_DEFAULT_CAPTURE_MODE (lambda) = CPLD_NONE;
  LAMBDA_EXPR_CAPTURE_LIST (lambda) = NULL_TREE;
  LAMBDA_EXPR_THIS_CAPTURE (lambda) = NULL_TREE;
  LAMBDA_EXPR_PENDING_PROXIES (lambda) = NULL;
  LAMBDA_EXPR_RETURN_TYPE (lambda) = NULL_TREE;
  LAMBDA_EXPR_MUTABLE_P (lambda) = false;
  return lambda;
}
{% endhighlight %}

mutable\_p 应该就是 lambda 带不带 mutable 了，capture\_list, this\_capture 这些都可以意会到。
大概可以看到 lambda 表达式所需要的几个东东，capture mode, pending proxies 这几个一眼看去不知道是干嘛的，我们接着刚才的 parse 过程看好了。

首先确定 lambda expr 在源文件中的 location。

接着做 cp\_unevaluated\_operand 判断，如果不为 0 且之前没有报错的话，现在报错。

line 258
{% highlight cpp %}
/* Nonzero if we are parsing an unevaluated operand: an operand to
   sizeof, typeof, or alignof. */
int cp_unevaluated_operand;
{% endhighlight %}

也就是说 lambda 是不可以放在 sizeof, typeof, alignof 这几个里面的，我们随便写个程序试一下，当然会报错。

> ~ $ g++ -std=c++11 test.cpp
> test.cpp: In function ‘int main()’:
> test.cpp:47:20: error: lambda-expression in unevaluated context
>      cout &lt;&lt; sizeof(\[\]() { return 1; }) &lt;&lt; endl;

> The evaluation of a lambda-expression results in a prvalue temporary (12.2). This temporary is called the closure object. A lambda-expression shall not appear in an unevaluated operand (Clause 5). \[ Note: A closure object behaves like a function object (20.8).—end note \] (emphasis mine)

错误处理之后，push\_deferring\_access\_checks 推迟 access check ，（gcc/cp/semantics.c）因为我们现在还不知道 capture list呢。

{% highlight cpp %}
  /* We may be in the middle of deferred access check. Disable
     it now. */
  push_deferring_access_checks (dk_no_deferred);
{% endhighlight %}

接着开始 parse introducer

{% highlight cpp %}
cp_parser_lambda_introducer (parser, lambda_expr);
{% endhighlight %}

line 8833
{% highlight cpp %}
  /* Need commas after the first capture. */
  bool first = true;
  /* Eat the leading `['. */
  cp_parser_require (parser, CPP_OPEN_SQUARE, RT_OPEN_SQUARE);
  /* Record default capture mode. "[&" "[=" "[&," "[=," */
  if (cp_lexer_next_token_is (parser->lexer, CPP_AND)
      && cp_lexer_peek_nth_token (parser->lexer, 2)->type != CPP_NAME)
    LAMBDA_EXPR_DEFAULT_CAPTURE_MODE (lambda_expr) = CPLD_REFERENCE;
  else if (cp_lexer_next_token_is (parser->lexer, CPP_EQ))
    LAMBDA_EXPR_DEFAULT_CAPTURE_MODE (lambda_expr) = CPLD_COPY;
  if (LAMBDA_EXPR_DEFAULT_CAPTURE_MODE (lambda_expr) != CPLD_NONE)
    {
      cp_lexer_consume_token (parser->lexer);
      first = false;
    }
{% endhighlight %}

原来 capture mode 就是指 &, = 这些 capture 的方式。
上面都是在做一些 cosume token 的工作，我们接着看。

{% highlight cpp %}
  while (cp_lexer_next_token_is_not (parser->lexer, CPP_CLOSE_SQUARE))
{% endhighlight %}

恩要开始 parse capture list 了。 细节就不追求，我们看几个关键的。

{% highlight cpp %}
enum capture_kind_type
{
  BY_COPY,
  BY_REFERENCE
};
 /* Possibly capture `this'. */
if (cp_lexer_next_token_is_keyword (parser->lexer, RID_THIS))
  {
    location_t loc = cp_lexer_peek_token (parser->lexer)->location;
    if (LAMBDA_EXPR_DEFAULT_CAPTURE_MODE (lambda_expr) == CPLD_COPY)
      pedwarn (loc, 0, "explicit by-copy capture of %<this%> redundant "
               "with by-copy capture default");
    cp_lexer_consume_token (parser->lexer);
    add_capture (lambda_expr,
                 /*id=*/this_identifier,
                 /*initializer=*/finish_this_expr(),
                 /*by_reference_p=*/false,
                 explicit_init_p);
    continue;
  }
{% endhighlight %}

这是 capture this 指针的情况。注意到在后面还有

{% highlight cpp %}
add_capture (lambda_expr,
             capture_id,
             capture_init_expr,
             /*by_reference_p=*/capture_kind == BY_REFERENCE,
             explicit_init_p);
{% endhighlight %}

看来问题的关键是看 add\_capture 是怎么做的。

lambda.c 
line 439
{% highlight cpp %}
tree
add_capture (tree lambda, tree id, tree orig_init, bool by_reference_p,
             bool explicit_init_p)
{% endhighlight %}

参数分别是 lambda\_expr， capture 到的 identifier，initializer， 是否按引用传递。
最后一个 explicit\_init\_p，可以看到在 parse 的 while loop 里面，一开始是被设成 false 的。

什么时候是 true 呢，在 whilte loop 的中间有这样一段：

line 8934
{% highlight cpp %}
/* Find the initializer for this capture. */
if (cp_lexer_next_token_is (parser->lexer, CPP_EQ)
    || cp_lexer_next_token_is (parser->lexer, CPP_OPEN_PAREN)
 cp_lexer_next_token_is (parser->lexer, CPP_OPEN_BRACE))
  {
    bool direct, non_constant;
    /* An explicit initializer exists. */
    if (cxx_dialect < cxx1y)
      pedwarn (input_location, 0,
               "lambda capture initializers "
               "only available with -std=c++1y or -std=gnu++1y");
    capture_init_expr = cp_parser_initializer (parser, &direct,
                                               &non_constant);
    explicit_init_p = true;
    if (capture_init_expr == NULL_TREE)
      {
        error ("empty initializer for lambda init-capture");
        capture_init_expr = error_mark_node;
      }
  }
else
{% endhighlight %}

也就是说，explicit\_init\_p 是说是否进行初始化，因为可能lambda catpure 到了一个在上面进行构造的对象。
这是 c++1y 的特性喔。
比如说 

{% highlight cpp %}
auto lambda = [value = 1] {return value;};
 
auto ptr = std::make_unique<int>(10); // See below for std::make_unique auto lambda = [ptr = std::move(ptr)] {return *ptr;};
{% endhighlight %}
explicit\_init\_p 也就是干这个用的，当存在 initializer 时为 true。
不过，看到 /*initializer=*/finish\_this\_expr(), this 的 initializer 有什么猫腻么？ 跟进去看一下。         

semantics.c
line 2426
{% highlight cpp %}
tree
finish_this_expr (void)
{
  tree result;
  if (current_class_ptr)
    {
      tree type = TREE_TYPE (current_class_ref);
      /* In a lambda expression, 'this' refers to the captured 'this'. */
      if (LAMBDA_TYPE_P (type))
        result = lambda_expr_this_capture (CLASSTYPE_LAMBDA_EXPR (type));
      else
        result = current_class_ptr;
    }
  else if (current_function_decl
           && DECL_STATIC_FUNCTION_P (current_function_decl))
    {
{% endhighlight %}

竟然有对 lambda 表达式的特殊处理，来看 lambda\_expr\_this\_capture。

lambda.c line 626
{% highlight cpp %}
/* Return the capture pertaining to a use of 'this' in LAMBDA, in the form of an
   INDIRECT_REF, possibly adding it through default capturing. */
tree
lambda_expr_this_capture (tree lambda)
{% endhighlight %}

这里的代码有些复杂，暂时不仔细追求，以免影响了理解 lambda 的大局。不过可以看一下注释

{% highlight cpp %}
/* If we are in a lambda function, we can move out until we hit:
     1. a non-lambda function or NSDMI,
     2. a lambda function capturing 'this', or
     3. a non-default capturing lambda function. */
{% endhighlight %}

原来他是在费尽心思做这种事情。
我们现在还在 finish\_this\_expr -&gt; lambda\_expr\_this\_capture 上。 不过已经大概清楚这一步是想找到适合的 this。

刚才是 this 指针的 initializer （orig\_init 参数）， 那普通的变量 capture 这个要穿什么呢?

之前我们有看到 c++1y 的奇妙 lambda initializer expression，不过对于一般情况呢？
接着上面 whilte loop 中的 else

parser.c line 8943
{% highlight cpp %}
          /* Turn the identifier into an id-expression. */
          capture_init_expr
            = cp_parser_lookup_name_simple (parser, capture_id,
                                            capture_token->location);
{% endhighlight %}

开始做 name lookup 了，看看这个东西之前有没有定义过。接下来是一些关于 capture 到的 id 的一些性质上的判断。

{% highlight cpp %}
if (capture_init_expr == error_mark_node)
  {
    unqualified_name_lookup_error (capture_id);
    continue;
  }
else if (DECL_P (capture_init_expr)
         && (!VAR_P (capture_init_expr)
             && TREE_CODE (capture_init_expr) != PARM_DECL))
  {
    error_at (capture_token->location,
              "capture of non-variable %qD ",
              capture_init_expr);
    inform (0, "%q+#D declared here", capture_init_expr);
    continue;
  }
if (VAR_P (capture_init_expr)
    && decl_storage_duration (capture_init_expr) != dk_auto)
  {
    if (pedwarn (capture_token->location, 0, "capture of variable "
                 "%qD with non-automatic storage duration",
                 capture_init_expr))
      inform (0, "%q+#D declared here", capture_init_expr);
    continue;
  }
{% endhighlight %}

 最后来到这里，

{% highlight cpp %}
capture_init_expr
            = finish_id_expression
                (capture_id,
                 capture_init_expr,
                 parser->scope,
                 &idk,
                 /*integral_constant_expression_p=*/false,
                 /*allow_non_integral_constant_expression_p=*/false,
                 /*non_integral_constant_expression_p=*/NULL,
                 /*template_p=*/false,
                 /*done=*/true,
                 /*address_p=*/false,
                 /*template_arg_p=*/false,
                 &error_msg,
                 capture_token->location);
{% endhighlight %}

再往后就是一些简单的逻辑，暂且不看。记得刚才也有 finish_this_expr，而这里有一个 finish_id_expression。
看来一个 identifier 总是要 finish 一下，跟他之前的声明做 binding。来看一下 finish_id_expression

semantics.c 3093

具体的代码就不贴了。以免脱离主题。我们还是回到 add_capture 上来。
基于相似的理由，add_capture 的代码还是不贴了（太长）。大致的逻辑是根据传进来的参数构建 capture list 的 parse tree。

似乎在 cp_parser_lambda_introducer 上耗费了太长的时间，一直都没进入真正的主题。
不过怎么说，也算熟悉了一下 gcc 的套路（顺便吐槽一下模块真是太乱了）

parser.c line 8741
{% highlight cpp %}
  /* We may be in the middle of deferred access check. Disable
     it now. */
  push_deferring_access_checks (dk_no_deferred);
  cp_parser_lambda_introducer (parser, lambda_expr);
  type = begin_lambda_type (lambda_expr);
  if (type == error_mark_node)
    return error_mark_node;
  record_lambda_scope (lambda_expr);
  /* Do this again now that LAMBDA_EXPR_EXTRA_SCOPE is set. */
  determine_visibility (TYPE_NAME (type));
  /* Now that we've started the type, add the capture fields for any
     explicit captures. */
  register_capture_members (LAMBDA_EXPR_CAPTURE_LIST (lambda_expr));
{% endhighlight %}

唉，慢慢长征，我们刚刚只是过了一下   cp\_parser\_lambda\_introducer。不过对于 lambda 来说，introducer 之后就是 function，function parse 的过程我们就不必关心了。所以路程应该已经走了一半。

lambda.c line 127
{% highlight cpp %}
begin_lambda_type (tree lambda)
{
  tree type;
  {
    /* Unique name. This is just like an unnamed class, but we cannot use
       make_anon_name because of certain checks against TYPE_ANONYMOUS_P. */
    tree name;
    name = make_lambda_name ();
    /* Create the new RECORD_TYPE for this lambda. */
    type = xref_tag (/*tag_code=*/record_type,
                     name,
                     /*scope=*/ts_lambda,
                     /*template_header_p=*/false);
    if (type == error_mark_node)
      return error_mark_node;
  }
  /* Designate it as a struct so that we can use aggregate initialization. */
  CLASSTYPE_DECLARED_CLASS (type) = false;
  /* Cross-reference the expression and the type. */
  LAMBDA_EXPR_CLOSURE (lambda) = type;
  CLASSTYPE_LAMBDA_EXPR (type) = lambda;
  /* Clear base types. */
  xref_basetypes (type, /*bases=*/NULL_TREE);
  /* Start the class. */
  type = begin_class_definition (type);
  return type;
}
{% endhighlight %}

这里我们给 lambda 一个具体的类型，怎样的类型呢？ 就在 xref\_tag 那里，跟进去看

decl.c line 12183
{% highlight cpp %}
tree
xref_tag (enum tag_types tag_code, tree name,
          tag_scope scope, bool template_header_p)
{
  tree ret;
  bool subtime;
  subtime = timevar_cond_start (TV_NAME_LOOKUP);
  ret = xref_tag_1 (tag_code, name, scope, template_header_p);
  timevar_cond_stop (TV_NAME_LOOKUP, subtime);
  return ret;
}
{% endhighlight %}

又是代理，我们继续跟。

decl.c line 12038
{% highlight cpp %}
static tree
xref_tag_1 (enum tag_types tag_code, tree name,
            tag_scope orig_scope, bool template_header_p)
{
  enum tree_code code;
  tree t;
  tree context = NULL_TREE;
  tag_scope scope;
  gcc_assert (identifier_p (name));
  switch (tag_code)
    {
    case record_type:
    case class_type:
      code = RECORD_TYPE;
      break;
{% endhighlight %}

真是是 struct ！ 在 gcc 内部，struct 被叫成了 record。于是我们已经知道了 lambda 究竟是怎样的东西~
当然在后面，我们会找到对应的

{% highlight cpp %}
 type = finish_struct (type, /*attributes=*/NULL_TREE); 
{% endhighlight %}

继续看关键的 register\_capture\_members

lambda.c line 567
{% highlight cpp %}
/* Register all the capture members on the list CAPTURES, which is the
   LAMBDA_EXPR_CAPTURE_LIST for the lambda after the introducer. */
void
register_capture_members (tree captures)
{
  if (captures == NULL_TREE)
    return;
  register_capture_members (TREE_CHAIN (captures));
  tree field = TREE_PURPOSE (captures);
  if (PACK_EXPANSION_P (field))
    field = PACK_EXPANSION_PATTERN (field);
  /* We set this in add_capture to avoid duplicates. */
  IDENTIFIER_MARKED (DECL_NAME (field)) = false;
  finish_member_declaration (field);
}
{% endhighlight %}

递归注册所有 capture 成员，因为递归搞反了顺序，后面还有相应的 reverse 修正。
而这一步把 capture list 的各个东东都注册成了 record parse tree 的 node，也就是说，成为了 lambda 这个 struct 的 member。

继续往后看，忽略中间的细节。

{% highlight cpp %}
  pop_deferring_access_checks ();
  /* This field is only used during parsing of the lambda. */
  LAMBDA_EXPR_THIS_CAPTURE (lambda_expr) = NULL_TREE;
  /* This lambda shouldn't have any proxies left at this point. */
  gcc_assert (LAMBDA_EXPR_PENDING_PROXIES (lambda_expr) == NULL);
  /* And now that we're done, push proxies for an enclosing lambda. */
  insert_pending_capture_proxies ();
  if (ok)
    return build_lambda_object (lambda_expr);
  else
    return error_mark_node;
{% endhighlight %}

注意到 insert\_pending\_capture\_proxies，这应该是对应之前我们所不知道的 LAMBDA\_EXPR\_PENDING\_PROXIES 。
还是在 lambda.c 里面

{% highlight cpp %}
/* We've just finished processing a lambda; if the containing scope is also
   a lambda, insert any capture proxies that were created while processing
   the nested lambda. */
void
insert_pending_capture_proxies (void)
{
  tree lam;
  vec<tree, va_gc> *proxies;
  unsigned i;
  if (!current_function_decl || !LAMBDA_FUNCTION_P (current_function_decl))
    return;
  lam = CLASSTYPE_LAMBDA_EXPR (DECL_CONTEXT (current_function_decl));
  proxies = LAMBDA_EXPR_PENDING_PROXIES (lam);
  for (i = 0; i < vec_safe_length (proxies); ++i)
    {
      tree var = (*proxies)[i];
      insert_capture_proxy (var);
    }
  release_tree_vector (LAMBDA_EXPR_PENDING_PROXIES (lam));
  LAMBDA_EXPR_PENDING_PROXIES (lam) = NULL;
}
{% endhighlight %}

再看具体做事的 insert\_capture\_proxy

{% highlight cpp %}
/* VAR is a capture proxy created by build_capture_proxy; add it to the
   current function, which is the operator() for the appropriate lambda. */
void
insert_capture_proxy (tree var)
{
  cp_binding_level *b;
  tree stmt_list;
  /* Put the capture proxy in the extra body block so that it won't clash
     with a later local variable. */
  b = current_binding_level;
  for (;;)
    {
      cp_binding_level *n = b->level_chain;
      if (n->kind == sk_function_parms)
        break;
      b = n;
    }
  pushdecl_with_scope (var, b, false);
  /* And put a DECL_EXPR in the STATEMENT_LIST for the same block. */
  var = build_stmt (DECL_SOURCE_LOCATION (var), DECL_EXPR, var);
  stmt_list = (*stmt_list_stack)[1];
  gcc_assert (stmt_list);
  append_to_statement_list_force (var, &stmt_list);
}
{% endhighlight %}

原来是往里面放了一个 declaration statement，声明变量。似乎有些搞不懂这个 proxy 是做什么的，难道是之前我们跳跃的太快漏掉了什么？

发现还存在以下的调用关系 add\_capture -&gt; build\_capture\_proxy -&gt; insert\_capture\_proxy 。

因为已经看的累了，就一遍看注释一遍 yy 吧。

{% highlight cpp %}
/* MEMBER is a capture field in a lambda closure class. Now that we're
   inside the operator(), build a placeholder var for future lookups and
   debugging. */
tree
build_capture_proxy (tree member)
{% endhighlight %}

原来 proxy 就是对 capture list 中成员的 proxy。而为什么有 pending 的呢？ 就是因为存在 capture & = 这样的情况，要在之后才能 resolve。

最后看 build\_lambda\_object，已经是在做一些收尾工作，给 lamabda 添加 ctor 等等 。。。

至此，终于简要的过了一遍 lambda 的实现。lambda 功能都是在前端 parser 时候做的（甜甜的语法糖），索性我们不用看后端的代码~ 其实看得有点烂尾，因为 add\_capture 里面的东西还是没有仔细研究，看这个代码真的很累很累 = =

### 总结一下~
1. 对于一个大项目来说，看代码并不是一件难事。grep 在手天下我有。只要抓住某条线不放总能找到蛛丝马迹。
2. 如果想深入了解每一个细节还是有难度的，主要还是精力问题。所以看代码的时候要进得去出的来，千万别抱死在某个函数上。
3. C 的代码确实很难看，很难看，还好 gcc 的注释够给力。
4. 一句话总结 lambda，带 operator() 的 struct。