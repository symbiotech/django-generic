(
    function($){
        $(document).ready(function(){
            window.update_cooked_field = function(field){
                $(field).hide();
                var container = $(field).closest('div');
                $('.help', container).html(
                    'Click cross icons to remove existing items, ' +
                    'or magnifying glass icon to add more.'
                );
                var field_name = $(field).attr('name');
                var ids = escape($(field).val());
                if (ids){
                    var url_base = window.cooked_id_url_base || '../';
                    var cook_url =
                        url_base + 'cook-ids/' + field_name + '/' + ids + '/';
                    $.get(cook_url, function(response){
                        var cooked = $('.cooked-data', container);
                        cooked.html('');
                        $.each(response, function(key, data){
                        $('<li data-id="'+key+'"></li>').text(data['text']).append(
                            ' <a onclick="remove_cooked_item(this);"' +
                            ' title="remove">&nbsp;</a>'
                        ).appendTo(cooked);
                        
                        if(data['can_view'] || data['can_edit'])
                        {
							var options = {};
							if(data['can_view'])
							{
									options['View'] = {click: function(element) {  
											window.location.href = data['can_view'];
										}
									}
							}
							if(data['can_edit'])
							{
									options['Edit'] = {click: function(element) {  
											window.location.href = data['base_url'] + key + '/';
										}
									}
							}
							
							$('li[data-id='+key+']').contextMenu('context-menu-'+key, options);
						}                        
                        
                        });
                    });
                }
            }

            window.remove_cooked_item = function(remove_link){
                var li = $(remove_link).parent();
                var id_to_remove = $(li).attr('data-id'); // jQuery only 1.4.2
                var container = $(li).closest('div');
                var field = $('.CookedIdField', container);
                var values = $(field).val().split(',');
                $(field).val(
                    $.grep(
                        values, function(id){ return id != id_to_remove }
                    ).join(',')
                );
                update_cooked_field(field);
                $(li).remove();
            }

            var originalDismissRelated = window.dismissRelatedLookupPopup;
            window.dismissRelatedLookupPopup = function(win, chosenId){
                originalDismissRelated(win, chosenId);
                $(window).trigger('dismissRelatedLookupPopup');
            }

            var originalDismissAddAnother = window.dismissAddAnotherPopup;
            window.dismissAddAnotherPopup = function(win, newId, newRepr){
                originalDismissAddAnother(win, newId, newRepr);
                $(window).trigger('dismissAddAnotherPopup');
            }

            $('.CookedIdField').each(
                function(index, element){
                    update_cooked_field(element);
                    $(element).bind(
                        'change', function(event){
                            update_cooked_field(event.target);
                        }
                    );
                }
            );
            $(window).bind('dismissRelatedLookupPopup', function(event){
                $('.CookedIdField').each(
                    function(index, element){
                        $(element).triggerHandler('change');
                    }
                );
            });
            $(window).bind('dismissAddAnotherPopup', function(event){
                $('.CookedIdField').each(
                    function(index, element){
                        $(element).triggerHandler('change');
                    }
                );
            });
        });
    }
)(django.jQuery);
