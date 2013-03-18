<?php
/* ****************************************************************** **
 * Function printsubmenu($seealso,$demos,$doctype)
 * 		print right menu composed of 
 * 			- switch link
 * 			- demos
 * 			- see also
 * 			- subtopic
 * Edit this function to create your template
 * 
 * Infos:
 * $doctype = 0 for contents.m file
 * $doctype = 1 for documentation
 * $doctype = 2 for code
 * 
 * Author: Nathanael Perraudin
 * Date:   18.03.2013
 * ****************************************************************** */
function printsubmenu($seealso,$demos,$doctype)
{
	echo'<div id="space"> </div>
	<div id="sidebar">';
	if ($doctype)
	{

		echo '<b>This function:</b><br>';
		print_switch_link($doctype); // function below
		
		
		
		print_demos($demos); // function below
		
		print_see_also($seealso); // function below

	}

	

	echo ' <div id="space"> </div>
	<b><u>Subtopics:</u></b><br>
	<hr />';
	print_subtopics(); // function below
	echo '</div>';
}


/* ****************************************************************** **
 * Function print_switch_link($doctype)
 * 		print the link to switch between documenation and code
 * ****************************************************************** */
function print_switch_link($doctype)
{
	$current_file_name = basename($_SERVER['REQUEST_URI'], ".php"); /* supposing filetype .php*/
	if ($doctype==1)
	{	
		echo '<a href="'.$current_file_name.'_code.php">Program code</a><br>';
	}
	
	if ($doctype==2)
	{	
		echo '<a href="'.substr($current_file_name, 0, strlen($current_file_name)-5).'.php">Help text</a><br>';
	}
}


/* ****************************************************************** **
 * Function print_see_also($seealso)
 * 		print the list of link for see also
 * ****************************************************************** */
function print_see_also($seealso)
{
	if (!empty($seealso))
	{
		echo '<hr />';
		echo '<div id="see_also_box">	
			<b>See also:</b> <ul>
			';
		
		foreach($seealso as $cle => $element)
		{
			echo '<li><a href='. $element.'>' . $cle.'</a></li>
			';
		}
		echo '</ul></div>';
	}
}


/* ****************************************************************** **
 * Function print_demos($demos)
 * 		print the list of demos
 * ****************************************************************** */
function print_demos($demos)
{
	if (!empty($demos))
	{ 
		echo '<hr />';
		echo '<div id="demos_box">	
			<b>Demos:</b> <ul>';
			
		foreach($demos as $cle => $element)
		{
			echo '<li><a href='. $element.'>' . $cle.'</a></li>
			';
		}
		echo '</ul></div>';
	}
	
}



/* ****************************************************************** **
 * Function print_subtopics()
 * 		print the subtopics
 * ****************************************************************** */
function print_subtopics()
{
	include("contentsmenu.php");
	
	$iter=0;
	foreach($menu as $cle => $element)
	{	

		if (substr($cle, 0, 7)=="caption")
		{
			if ($iter==0)
			{
				echo '<b>'.$element.'</b><ul>';	
				$iter=1;
			}
			else
			{
				echo '</ul><b>'.$element.'</b><ul>';
			}
			
		}
		else
		{
			echo '<li>'.$element.'</li>';
		}
	}
	echo '</ul>';
}


?>
