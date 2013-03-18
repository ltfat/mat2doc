<?php
/* ****************************************************************** **
 * Function print_header($title,$keywords)
 * 		print the header depending of keywords an title
 * 
 * Edit this function to create your template
 * 
 * Author: Nathanael Perraudin
 * Date:   18.03.2013
 * ****************************************************************** */
function print_header($title,$keywords)
{
	global $path_include;
	global $path_rel;
    echo '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN"><html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<META NAME="keywords" CONTENT="UNLocBoX, Matlab, optmization, convex, toolbox, '.$keywords.'"/> 
<title>'.$title.'</title>
<link rel="stylesheet" href="'.$path_include.'html4css1.css" type="text/css">
<link rel="stylesheet" href="'.$path_include.'mat2doc.css" type="text/css">
<link rel="stylesheet" href="'.$path_include.'color_text.css" type="text/css">
<script type="text/javascript"
   src="http://cdn.mathjax.org/mathjax/latest/MathJax.js?config=TeX-AMS-MML_HTMLorMML">
</script>
</head>
';


}
?>

